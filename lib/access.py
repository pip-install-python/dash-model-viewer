"""The access policy this site hands to dash-improve-my-llms.

One function matters — :func:`check` — and its *ordering* is the whole design:

    tier -> short-circuit public/hidden
         -> local Clerk session          (a person in a browser)
         -> hub verification of ?key=    (an agent, later, elsewhere)

**Local session first, hub only as a fallback.** A signed-in visitor is
resolved entirely on this host, so the hub being down gates nothing for them.
Only the agent path — a fetch with no cookie, carrying a key in the URL —
needs the hub at all. Reversing this order would couple every satellite's
availability to one host for no benefit: it is the single most consequential
line in this file.

Two questions get asked of a documentation site, and only one has a session
attached. Clerk answers "who is this human?". It can never answer "may this
fetch of a text file proceed?", because when someone pastes
``https://host/guide/llms.txt`` into an assistant, the fetch arrives with no
cookie. That is why authority has to be able to travel in the URL, and why
both mechanisms exist rather than one.

Unwired by default: :func:`configure` does nothing unless this deployment has
tiers that are not all public, so a fork inherits the machinery without
inheriting a gate it did not ask for.
"""

from __future__ import annotations

import logging
from typing import Optional

from lib import auth, hub_client, page_tiers

logger = logging.getLogger(__name__)


def _request_key() -> str:
    """The ``?key=`` on the current request, or "". Never raises, never logs."""
    try:
        from flask import request, has_request_context

        if not has_request_context():
            return ""
        return (request.args.get("key") or "").strip()
    except Exception:
        return ""


def effective_tier(path: str) -> str:
    """This page's tier, with the hub ceiling applied and degradation handled."""
    tier = page_tiers.effective_tier(path, hub_client.hub_tiers().get(path))
    if not auth.clerk_enabled():
        # No way to identify anyone: everything except `hidden` falls open.
        # See lib/page_tiers.degraded_tier for why that is the right trade
        # for reading documentation, and why admin surfaces don't rely on it.
        return page_tiers.degraded_tier(tier)
    return tier


def check(path: str) -> str:
    """``allow`` | ``gated`` | ``deny`` for the current request.

    Runs inside the request, on every request, on paths that may be hot — so
    it stays cheap: a dict lookup, and at most one cached hub call for the
    agent path.
    """
    tier = effective_tier(path)

    if tier == "hidden":
        return "deny"
    if tier == "public":
        return "allow"

    # A signed-in reader in a browser. Resolved here, without the hub.
    user = auth.current_user()
    if user is not None:
        if tier == "admin":
            return "allow" if auth.is_admin_user(user) else "gated"
        return "allow"

    # No session: an agent, or an anonymous browser. Only a key can help now.
    key = _request_key()
    if not key:
        return "gated"
    return hub_client.verify(key, path, tier)


def gate_doc(path: str) -> str:
    """The Markdown an unauthorised reader receives at 200.

    Deliberately useful rather than a wall: it names the page, says what would
    unlock it and where to sign in. An agent that fetches a gated document
    should come away knowing what it is and how its user gets access — that is
    the difference between a gate and a dead end, and it is why `gated` keeps
    the URL listed in the index and sitemap.
    """
    tier = effective_tier(path)
    name = _page_name(path) or path
    sign_in = _sign_in_url()

    lines = [
        f"# {name}",
        "",
        "> This document exists but is not public.",
        "",
        "---",
        "",
    ]
    if tier == "admin":
        lines += ["Reading it requires an administrator account on this site."]
    else:
        lines += ["Reading it requires a signed-in account."]
    lines += [
        "",
        "**If you are a person:** sign in"
        + (f" at {sign_in}" if sign_in else "")
        + ", then reload this page.",
        "",
        "**If you are an assistant:** ask whoever gave you this URL to copy it "
        "again while signed in. The copied link carries a key that authorises "
        "this document, and it will work when pasted here.",
        "",
        "The page's existence is public; only its content is restricted.",
        "",
    ]
    return "\n".join(lines)


def link_suffix() -> str:
    """Carry authority to the links generated in *this* response.

    An agent handed an authorised URL must be able to follow the site-index
    and per-page links inside it, or the catalogue is untraversable one hop
    from the document it was given. The package appends this to same-origin
    generated URLs only — never to canonical tags, the sitemap, or peer hosts,
    because a capability should not travel to another origin.
    """
    key = _request_key()
    return f"?key={key}" if key else ""


def _page_name(path: str) -> Optional[str]:
    try:
        import dash

        for entry in dash.page_registry.values():
            if page_tiers.normalize(entry.get("path", "")) == page_tiers.normalize(path):
                return entry.get("name")
    except Exception:
        pass
    return None


def _sign_in_url() -> Optional[str]:
    import os

    return (os.getenv("CLERK_SIGN_IN_URL") or "").strip() or None


def gating_configured() -> bool:
    """True when at least one page is not public.

    A site whose pages are all public gains nothing from a per-request check
    and pays for it on every hot path, so the wiring stays off until a tier
    says otherwise.
    """
    return any(tier != "public" for tier in page_tiers.registered().values())


def configure(force: bool = False) -> bool:
    """Hand the policy to the package. Returns True when access control is on.

    Call after the pages are registered — the decision depends on their tiers.
    """
    if not (force or gating_configured()):
        return False

    from dash_improve_my_llms import configure_access, configure_viewer_identity

    configure_access(check, gate_doc=gate_doc, link_suffix=link_suffix)
    configure_viewer_identity(auth.viewer_identity)
    logger.info(
        "access control ON (clerk=%s, hub=%s)",
        auth.clerk_enabled(),
        hub_client.enabled(),
    )
    return True
