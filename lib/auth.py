"""Optional Clerk authentication — this site as a Clerk satellite.

Adapted from ``2plot_leaflet/lib/auth.py``, the implementation already sharing
authenticated state across ``2plot.ai`` → ``2plot.dev`` → ``leaflet.2plot.dev``
in production. Every satellite forked from this template should inherit this
file rather than reimplement it; the satellite fixups below in particular were
each found the hard way.

FULLY OPTIONAL. With no ``CLERK_*`` keys in the environment — or the package
missing, which is the default, because ``dash-clerk-auth`` is not on PyPI — the
site runs exactly as it does without this module: no script injection, no
session machinery, no routes, and every page tier falls open to public. That is
deliberate. A component library's documentation must never brick because a
deploy forgot a key. The single source of truth for "is auth on" is
:func:`clerk_enabled`.

Env vars (set all three to enable):
    CLERK_SECRET_KEY       sk_...  backend SDK key, never exposed to the client
    CLERK_PUBLISHABLE_KEY  pk_...  embedded in the injected <script>
    CLERK_SIGN_IN_URL      https://2plot.ai/sign-in   (the primary hosts sign-in)

Required in production (warned about loudly when missing):
    SESSION_SECRET         signs the session cookies. Without it dash-clerk-auth
                           falls back to a PUBLIC dev default.
    CLERK_FRONTEND_API     https://<app>.clerk.accounts.dev — REQUIRED in
                           satellite mode. Production custom-domain instances
                           cannot derive it from CLERK_SIGN_IN_URL.

Satellite config:
    CLERK_IS_SATELLITE     "true" in prod. Leave false locally — Clerk rejects
                           satellites on localhost.
    CLERK_SATELLITE_DOMAIN host only, no scheme. Defaults to the host in
                           APP_BASE_URL, which every deployment must set
                           anyway (see lib/constants.py).
    CLERK_SIGN_UP_URL      https://2plot.ai/sign-up

Admin allowlist:
    ADMIN_EMAILS           comma-separated, case-insensitive
    ADMIN_USER_IDS         comma-separated, case-insensitive
    OWNER_EMAIL            always counts as admin

Dev kill switch:
    DISABLE_CLERK=1        reads as "intentionally off" without touching the
                           CLERK_* values — the reliable way to run an auth-off
                           session when a shell env prefix doesn't survive an
                           IDE run configuration. Never set in production.

NOTE: read env at CALL time, not import time. ``lib.backend``'s ``load_dotenv``
must have run first, and the tests blank env vars per process.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from lib.constants import BASE_URL

# The app owner's account. Gates owner-only surfaces; env-overridable so a fork
# is not permanently stuck with this template's owner.
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "pipinstallpython@gmail.com")


def satellite_host() -> str:
    """This deployment's own host, without a scheme.

    Derived from APP_BASE_URL rather than hardcoded: that value is already
    mandatory per deployment (`require_owned_base_url`), so deriving it here
    means a fork has one fewer thing to remember — and one fewer way to end up
    announcing another site's domain to Clerk.
    """
    return (os.getenv("CLERK_SATELLITE_DOMAIN") or urlparse(BASE_URL).netloc).strip()


def clerk_keys() -> tuple[str | None, str | None, str | None]:
    """(secret, publishable, sign_in_url) — or all None when disabled."""
    if (os.getenv("DISABLE_CLERK") or "").strip() == "1":
        return (None, None, None)
    return (
        os.getenv("CLERK_SECRET_KEY"),
        os.getenv("CLERK_PUBLISHABLE_KEY"),
        os.getenv("CLERK_SIGN_IN_URL"),
    )


def clerk_enabled() -> bool:
    """True only when all three CLERK_* vars are set AND the package imports."""
    if not all(clerk_keys()):
        return False
    try:
        import dash_clerk_auth  # noqa: F401

        return True
    except Exception:
        return False


def current_user():
    """The signed-in Clerk user, or None. Never raises."""
    if not clerk_enabled():
        return None
    try:
        from dash_clerk_auth import current_user as _current_user

        return _current_user()
    except Exception:
        return None


def current_user_email() -> str | None:
    user = current_user()
    return (getattr(user, "email", None) or None) if user else None


def _split_csv(raw: str | None) -> set[str]:
    return {item.strip().lower() for item in (raw or "").split(",") if item.strip()}


def admin_access_open() -> bool:
    """May admin surfaces render while Clerk is unavailable? Default **False**.

    The rest of this module fails open by design: with no Clerk keys every tier
    degrades to public, because documentation must never brick over a missing
    credential. That is the right trade for *reading* docs. It is the wrong
    trade for anything that can change what the site exposes — falling open
    there means whoever guesses the URL gets it.

    Set ``ALLOW_UNGATED_ADMIN=1`` to work on admin surfaces locally.
    """
    return (os.getenv("ALLOW_UNGATED_ADMIN") or "").strip() == "1"


def is_admin_user(user=None) -> bool:
    """Email / user-id allowlist, case-insensitive.

    The owner's email always counts, so a deploy that set the Clerk keys but
    forgot ADMIN_EMAILS still lets the owner in.
    """
    if user is None:
        user = current_user()
    if not user:
        return False
    admin_emails = _split_csv(os.getenv("ADMIN_EMAILS")) | {OWNER_EMAIL.lower()}
    admin_ids = _split_csv(os.getenv("ADMIN_USER_IDS"))
    email = (getattr(user, "email", None) or "").lower()
    if email and email in admin_emails:
        return True
    user_id = (getattr(user, "user_id", None) or "").lower()
    return bool(user_id and user_id in admin_ids)


# ---------------------------------------------------------------------------
# Viewer identity for the llms.txt banner
# ---------------------------------------------------------------------------

# session_id -> first ISO timestamp this process saw it. Deliberately NOT the
# Clerk token's `iat`: the session token is refreshed roughly every 60 seconds,
# so `iat` is the age of the *token*, not of the sign-in — wiring it renders a
# "signed in since" clock that resets every minute.
#
# Process-local and unbounded-by-design is wrong, so it is capped. Losing an
# entry costs a slightly-late timestamp, nothing more.
_SESSION_FIRST_SEEN: dict[str, str] = {}
_SESSION_CACHE_MAX = 2048


def _first_seen(session_id: str) -> str:
    from datetime import datetime, timezone

    stamp = _SESSION_FIRST_SEEN.get(session_id)
    if stamp is None:
        if len(_SESSION_FIRST_SEEN) >= _SESSION_CACHE_MAX:
            _SESSION_FIRST_SEEN.clear()
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _SESSION_FIRST_SEEN[session_id] = stamp
    return stamp


def viewer_identity() -> dict | None:
    """For ``configure_viewer_identity``. None when nobody is signed in.

    Rendered in the HTML viewer's banner only — the Markdown variant of the
    same URL is byte-identical with and without it, so this can never reach an
    agent, a crawler or an index.
    """
    user = current_user()
    if not user:
        return None
    try:
        identity = {"name": getattr(user, "email", None) or getattr(user, "user_id", "")}
        session_id = getattr(user, "session_id", None)
        if session_id:
            identity["since"] = _first_seen(session_id)
        plan = getattr(user, "plan", None)
        if plan:
            identity["plan"] = plan
        return identity if identity.get("name") else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Registration — MUST run BEFORE Dash() is constructed
# ---------------------------------------------------------------------------


def register() -> bool:
    """Register Clerk with Dash. Call this *before* ``Dash(...)``.

    ``register_clerk_auth`` installs ``@dash.hooks`` callbacks that fire during
    app construction, so calling it afterwards silently does nothing.

    Returns True when auth was actually wired up.
    """
    if not clerk_enabled():
        return False

    from dash_clerk_auth import register_clerk_auth

    secret, publishable, sign_in = clerk_keys()
    sat_domain = satellite_host() or None
    sat_env = (os.getenv("CLERK_IS_SATELLITE", "false").strip().lower() == "true")
    pk_live = (publishable or "").startswith("pk_live_")

    # A production (pk_live) instance served on a configured satellite domain
    # MUST init ClerkJS with isSatellite+domain, or ClerkJS throws "a satellite
    # application needs to specify a domain". Auto-enable it there even when
    # CLERK_IS_SATELLITE was missed in the deploy env, so production cannot
    # silently boot in primary mode. Local dev uses a pk_test key and stays
    # primary — Clerk rejects satellites on localhost.
    is_satellite = sat_env or (pk_live and bool(sat_domain))
    if is_satellite and not sat_domain:
        print(
            "[auth] WARNING: Clerk satellite mode needs a domain and none could "
            "be derived from APP_BASE_URL. Booting in PRIMARY mode; client "
            "sign-in will fail until CLERK_SATELLITE_DOMAIN is set."
        )
        is_satellite = False

    register_clerk_auth(
        clerk_secret_key=secret,
        clerk_publishable_key=publishable,
        clerk_sign_in_url=sign_in,
        session_secret=os.getenv("SESSION_SECRET"),
        backend="auto",
        headless=True,
        is_satellite=is_satellite,
        satellite_domain=sat_domain,
        clerk_frontend_api=(os.getenv("CLERK_FRONTEND_API") or None),
        sign_up_url=(os.getenv("CLERK_SIGN_UP_URL") or None),
    )

    if not os.getenv("SESSION_SECRET"):
        print(
            "[auth] WARNING: Clerk ENABLED but SESSION_SECRET unset — cookies "
            "would use dash-clerk-auth's PUBLIC dev default. Set it before "
            "deploying."
        )
    if pk_live and not is_satellite:
        print(
            "[auth] WARNING: pk_live key but NOT satellite mode — set "
            f"CLERK_SATELLITE_DOMAIN={sat_domain or 'your.host'} and "
            "CLERK_IS_SATELLITE=true, or ClerkJS will fail with "
            "'satellite needs a domain'."
        )

    if is_satellite and sat_domain:
        _install_satellite_fixups(sat_domain)

    print(
        f"[auth] Clerk ENABLED (headless; satellite={is_satellite}, "
        f"domain={sat_domain or '-'}, key={'live' if pk_live else 'test'})."
    )
    return True


def _install_satellite_fixups(sat_domain: str) -> None:
    """Two satellite fixes for dash-clerk-auth, applied via an index hook.

    1) clerk-js@5 reads ``domain`` as a CONSTRUCTOR option, from the script
       tag's ``data-clerk-domain`` — NOT as a ``load()`` option. 0.9.0 passed
       the domain only to ``Clerk.load({domain})``, so the hosted loader
       built the Clerk singleton with no domain and ``load({isSatellite:true})``
       threw "a satellite application needs to specify a domain or a proxyUrl".
       Fix: stamp ``data-clerk-domain`` onto the script tag. This hook runs
       after the package's, so the tag already exists. The vendored 0.9.1
       emits the attribute itself; the ``not in index_string`` guard below
       makes this a no-op there, and it stays for any fork still on 0.9.0.

    2) The package binds the sign-in button to ``Clerk.openSignIn()`` — a modal
       on the CURRENT domain. On a satellite that POSTs to the satellite FAPI's
       ``/sign_ins`` and 403s ("This operation is not allowed on a satellite
       domain"). Sign-in must redirect to the primary instead. Fix: intercept
       the ``#clerk-login-button`` click in the CAPTURE phase (it fires before
       the package's bubble-phase listener, and ``stopImmediatePropagation``
       prevents it) and call ``redirectToSignIn()``.

       ``signInForceRedirectUrl`` / ``signUpForceRedirectUrl`` point at THIS
       page so the primary returns the user here. The deprecated ``redirectUrl``
       prop is ignored by clerk-js@5, so without them the primary falls back to
       its own default and strands the user on the primary domain. Use
       origin+pathname with no query, so stale ``__clerk_*`` handshake params
       are not carried into the next sign-in.
    """
    from dash import hooks as _dash_hooks

    signin_js = (
        "<script>(function(){"
        "document.addEventListener('click',function(e){"
        "var b=e.target&&e.target.closest?e.target.closest('#clerk-login-button'):null;"
        "if(b&&window.Clerk&&typeof window.Clerk.redirectToSignIn==='function'){"
        "e.stopImmediatePropagation();e.preventDefault();"
        "var u=window.location.origin+window.location.pathname;"
        "window.Clerk.redirectToSignIn({signInForceRedirectUrl:u,signUpForceRedirectUrl:u});}"
        "},true);})();</script>"
    )

    @_dash_hooks.index()
    def _clerk_satellite_fixups(index_string):
        needle = "data-clerk-publishable-key="
        if needle in index_string and "data-clerk-domain=" not in index_string:
            index_string = index_string.replace(
                needle, f'data-clerk-domain="{sat_domain}" {needle}', 1
            )
        if "redirectToSignIn" not in index_string and "</body>" in index_string:
            index_string = index_string.replace("</body>", signin_js + "</body>", 1)
        return index_string


def configure_app(app) -> None:
    """Post-construction Clerk wiring (sessions, /api/auth/*, request identity).

    Separate from :func:`register` because dash-clerk-auth splits its setup
    either side of ``Dash(...)``. No-ops when auth is off.
    """
    if not clerk_enabled():
        return
    try:
        from dash_clerk_auth import configure_app as _configure

        _configure(app)
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001 — never break the boot on auth wiring
        print(f"[auth] WARNING: configure_app failed: {exc}")
