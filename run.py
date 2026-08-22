import inspect
import os
import sys
import dash
from dash import Dash
from components.appshell import create_appshell


def _version(text: str) -> tuple:
    """("4.4.1rc0") -> (4, 4, 1). Trailing rc/dev segments are dropped."""
    parts = []
    for chunk in text.split(".")[:3]:
        digits = ""
        for char in chunk:
            if not char.isdigit():
                break
            digits += char
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


# Feature gates below are keyed off this rather than off a try/except, so the
# reason a feature is unavailable is stated once, in one place.
DASH_VERSION = _version(dash.__version__)

# AI/LLM Integration & SEO — dash-improve-my-llms 2.2
# 2.0 replaced the custom Flask-only routes that used to live in this file
# (`/<page>/llms.txt`, `/<page>/page.json`, `/<page>/llms.toon`) with a single
# backend-detecting dispatcher covering Flask, FastAPI and Quart; `/page.json`
# and `/llms.toon` were dropped outright (Dash 4.3 MCP covers the structured
# introspection they were doing).
#
# 2.2 adds, on top of that: merge (not assign) semantics in
# register_page_metadata so no later call can erase a page's prose, a
# prerender that serves the content to every visitor rather than only to
# recognised crawlers, a Markdown renderer that emits real anchors/tables/code
# fences, and `register_network` — the cross-host directory fed by
# lib/network_directory.py below.
#
# Also new in 2.2: a page's llms.txt opens with a nav block back to the site
# and network indexes rather than being a dead end, and the same URL
# content-negotiates — Markdown for agents, a rendered view for browsers.
# (2.1 was assigned during development and never published; 2.0 upgrades
# straight to 2.2.)
from dash_improve_my_llms import (
    __version__ as LLMS_PKG_VERSION,
    add_llms_routes,
    LLMSConfig,
    RobotsConfig,
    register_page_metadata,
)

# The version requirements.txt pins. Checked at startup — see the floors block
# below for why this is worth a line of output on every boot.
#
# 2.3.4 is the network standard (2plot.ai and 2plot.dev both run it). Below it,
# `resolve_site_title` does not exist: the /llms.txt H1 and the llms-viewer
# brand chip fall back to `app.title` unconditionally, and a nav label or
# Dash's default "Dash" becomes this site's published identity.
# 2.6.1 is the floor. It unhides the prerendered body: the
# `#dimll-prerender` div used to ship with a `hidden` attribute, so every
# non-JS consumer — curl, unfurlers, agents without a browser engine — was
# handed prose that was technically present and explicitly invisible.
#
# 2.6.0 is what makes `lastmod=` on
# `register_page_metadata` reach the sitemap: below it the keyword is accepted
# into **kwargs and SILENTLY IGNORED, so every date this repo stamps is
# swallowed and <lastmod> reverts to invented build dates — a sitemap that
# swears all 10 pages changed today, every deploy. 2.6.0 also adds icon
# autodiscovery (this app still declares explicitly; the two must agree —
# tests/test_seo_icons.py), JSON-LD publisher.logo, and the viewer banner
# de-dup. `configure_seo` is deliberately imported AFTER this floor fires (see
# the floors block) so a stale environment gets the floor's diagnosis instead
# of a bare ImportError.
LLMS_PKG_FLOOR = (2, 6, 1)

# THE FORK POINT — claim this app's network identity before any hub-facing
# module imports. Every module that names this app (satellite_reporter,
# ad_client, hub_client, bulletin) carries its own fallback default, and after
# a template sync those defaults can DISAGREE: lib/satellite_reporter.py is
# byte-identical to the boilerplate's by contract, so ITS fallback says
# "boilerplate" while this fork's other modules say "modelviewer". An unset
# SATELLITE_APP_KEY would then file this site's traffic under the TEMPLATE's
# hub row (found live on pannellum, 2026-08-21). setdefault: a real env value
# (Render dashboard, .env) always wins — this line only closes the unset gap.
os.environ.setdefault("SATELLITE_APP_KEY", "modelviewer")

# Analytics tracking
from lib.analytics_tracker import tracker

# Site identity, public origin, and the cross-host network directory
from lib.constants import (
    APP_TITLE,
    BASE_URL,
    OG_IMAGE_ALT,
    OG_IMAGE_HEIGHT,
    OG_IMAGE_URL,
    OG_IMAGE_WIDTH,
    PUBLISHER,
    SAME_AS,
    SITE_BRAND,
    SITE_DESCRIPTION,
    require_owned_base_url,
)
from lib import network_directory

# Backend selection (flask | fastapi | quart) — see lib/backend.py
from lib.backend import resolve_backend, get_backend_info

scripts = [
    "https://unpkg.com/hotkeys-js/dist/hotkeys.min.js",
]

# ----------------------------------------------------------------------------
# Pluggable backend (Dash 4.1+)
# ----------------------------------------------------------------------------
BACKEND = resolve_backend()
BACKEND_INFO = get_backend_info(BACKEND)
IS_FLASK = BACKEND == "flask"

print(
    f"[boilerplate] Starting Dash {dash.__version__} "
    f"(dash-improve-my-llms {LLMS_PKG_VERSION}) on backend='{BACKEND}'"
)

# ----------------------------------------------------------------------------
# Dependency floors — enforced, not advised.
#
# These were warnings first. That was not enough: an IDE run configuration
# pointing at another project's virtualenv starts this app quite happily
# against whatever versions that environment holds, serves visibly older
# behaviour, and the warning scrolls past above a wall of page-loading logs.
# Diagnosing it from the outside costs hours — the browser, the cache and the
# process all look innocent, because they are.
#
# So a version below the floor stops the boot and says what to do. The app is
# never wrong-but-running. Set ALLOW_STALE_DEPS=1 to downgrade these to
# warnings if you are deliberately testing an older release.
# ----------------------------------------------------------------------------

ALLOW_STALE_DEPS = os.environ.get("ALLOW_STALE_DEPS", "0") == "1"


def _dependency_floor(message: str, fatal: bool) -> None:
    """Print, or refuse to start. Either way, name the interpreter.

    `sys.executable` is the fact that settles which environment is actually
    serving, and it is the one nobody thinks to check first.
    """
    detail = (
        f"{message}\n"
        f"    running from: {sys.executable}\n"
        f"    expected:     {os.path.join(os.path.dirname(os.path.abspath(__file__)), '.venv/bin/python')}\n"
        "    fix: point your run configuration at this project's own .venv, "
        "or reinstall with `pip install -r requirements.txt`.\n"
        "    (set ALLOW_STALE_DEPS=1 to start anyway)"
    )
    if fatal and not ALLOW_STALE_DEPS:
        raise RuntimeError("\n[boilerplate] " + detail)
    print("[boilerplate] WARNING: " + detail)


if LLMS_PKG_FLOOR > _version(LLMS_PKG_VERSION):
    _dependency_floor(
        f"dash-improve-my-llms {LLMS_PKG_VERSION} is below the "
        f"{'.'.join(str(n) for n in LLMS_PKG_FLOOR)} floor in requirements.txt. "
        "Below 2.6.1 the prerendered body ships with a `hidden` attribute, "
        "so every non-JavaScript consumer reads an empty page. Below "
        "2.6.0 the sitemap goes back to lying: `lastmod=` is accepted "
        "into **kwargs and SILENTLY IGNORED, so every date this repo stamped "
        "is swallowed and <lastmod> reverts to invented build dates. Below "
        "2.5.1 the Tier-B SEO standard additionally unwinds: `configure_seo` "
        "does not exist, the crawler <title> drops back to the bare page "
        "name, per-page title/image_url/schema_type never reach the crawler "
        "document, and /favicon.ico serves the app shell instead of an icon. "
        "Below 2.3.0 the rendered llms.txt viewer, wordmark and navigation "
        "block do not exist at all; below 2.3.4 this site's published identity "
        "silently degrades to whatever `app.title` happens to be.",
        fatal=True,
    )

# Imported after the floor on purpose: on a pre-2.5.0 package this name does
# not exist, and the floor's diagnosis above beats a bare ImportError. The
# fallback exists only for ALLOW_STALE_DEPS=1 — the floor is fatal otherwise.
try:
    from dash_improve_my_llms import configure_seo  # noqa: E402
except ImportError:  # pragma: no cover — ALLOW_STALE_DEPS with a pre-2.5.0 pkg

    def configure_seo(**_kwargs) -> None:
        print(
            "[boilerplate/modelviewer] WARNING: configure_seo unavailable "
            "(pre-2.5.0 package) — crawler identity tags and root icons "
            "not emitted."
        )


if DASH_VERSION < (4, 4):
    # Fatal only on FastAPI, where it is not a degradation but an outage:
    # 4.3.0's ASGI middleware returns before setting the request context, so
    # the page catch-all raises "No active request in context" and every
    # non-root URL 500s. Fixed upstream in 4.4.0. On Flask and Quart the same
    # Dash release works, so a warning is proportionate there.
    _dependency_floor(
        f"dash {dash.__version__} is below the 4.4.0 floor in requirements.txt."
        + (
            " On the FastAPI backend every non-root URL returns 500 "
            "('No active request in context') — an upstream defect in 4.3.0, "
            "fixed in 4.4.0."
            if BACKEND == "fastapi"
            else ""
        ),
        fatal=BACKEND == "fastapi",
    )

# Dash 4.3+ MCP server: exposes layout, components, pages and (whitelisted)
# callbacks to MCP clients over Streamable HTTP. Off unless DASH_MCP_ENABLED=1,
# because it is a live introspection surface on a public host.
#
# This has to be a constructor argument — Dash starts the server during
# __init__, so there is no supported way to switch it on afterwards.
# dash-improve-my-llms separately registers each page's prose as a `dash.mcp`
# resource, which is what gives an MCP client the docs alongside the
# introspection.
MCP_ENABLED = os.environ.get("DASH_MCP_ENABLED", "0") == "1"
MCP_PATH = os.environ.get("DASH_MCP_PATH", "_mcp")

# Passed as **kwargs rather than named arguments, because Dash validates
# unknown constructor keywords by raising TypeError. `enable_mcp` landed in
# 4.3, so naming it unconditionally makes the app refuse to boot on 4.2 with
# an error that says nothing about MCP — and the only thing being lost is a
# feature that is off by default anyway.
# ----------------------------------------------------------------------------
# Clerk satellite auth. MUST run BEFORE Dash(...) — register_clerk_auth
# installs @dash.hooks callbacks that fire during app construction, so calling
# it afterwards silently does nothing. Fully optional: a no-op with no CLERK_*
# keys, which is the default. See lib/auth.py.
# ----------------------------------------------------------------------------
from lib import auth as _auth  # noqa: E402

CLERK_ENABLED = _auth.register()

MCP_KWARGS = {}
if MCP_ENABLED:
    if "enable_mcp" in inspect.signature(Dash.__init__).parameters:
        MCP_KWARGS = {"enable_mcp": True, "mcp_path": MCP_PATH}
    else:
        print(
            f"[boilerplate] DASH_MCP_ENABLED=1 ignored: dash "
            f"{dash.__version__} has no MCP server (needs >= 4.3)."
        )

app = Dash(
    __name__,
    backend=BACKEND,
    title=APP_TITLE,
    suppress_callback_exceptions=True,
    use_pages=True,
    external_scripts=scripts,
    update_title=None,
    prevent_initial_callbacks=True,
    index_string=open('templates/index.html').read(),
    **MCP_KWARGS,
)

if MCP_KWARGS:
    print(
        f"[boilerplate] Dash MCP server enabled at /{MCP_PATH.lstrip('/')} "
        f"(dash {dash.__version__})."
    )

# dash-clerk-auth splits its setup either side of Dash(...): sessions, the
# /api/auth/* routes and per-request identity are wired here. No-op when off.
_auth.configure_app(app)

# ----------------------------------------------------------------------------
# Trust the proxy's forwarded scheme. Immediately after the server object
# exists and before anything can serve a request.
#
# Dash builds `twitter:url` from `request.url` for every page, and behind
# Cloudflare -> Render the last hop is plain HTTP, so production advertised
# `http://boilerplate.2plot.dev/` to every social scraper while `og:url` (which
# templates/index.html hard-codes) looked correct. Scrapers do not run
# JavaScript, so the client-side canonical sync in the template cannot reach
# this. See lib/proxy.py for why gunicorn's own forwarded-header handling does
# not cover it, and for the trust boundary.
# ----------------------------------------------------------------------------
from lib import proxy as _proxy  # noqa: E402

PROXY_FIX_APPLIED = _proxy.apply(app, BACKEND)
print(
    "[boilerplate] forwarded-scheme trust: "
    + ("on" if PROXY_FIX_APPLIED else "OFF — request.url will report the "
       "scheme of the last proxy hop, and social cards will advertise it")
)

# Expose backend info so layout components can render a badge without
# re-reading the env var (which could drift between processes/workers).
app._backend_info = BACKEND_INFO

# ============================================================================
# AI/LLM & SEO Configuration
# ============================================================================

# Public origin. Drives <link rel="canonical">, sitemap.xml and the absolute
# URLs in llms.txt — see lib/constants.py for why a fork that leaves this at
# the default deindexes itself, and set APP_BASE_URL per deployment.
require_owned_base_url()
app._base_url = BASE_URL

# Cross-host directory: <link rel="related"> tags, a "## Network" section in
# /llms.txt, and followed links in the prerendered body, so an agent that
# lands on one satellite can enumerate the rest. The peer list lives in
# lib/network_directory.py — one definition, imported by every satellite.
network_directory.apply(BASE_URL)

# Configure bot management policies — the balanced default this project
# documents: block training crawlers, allow AI search citations and
# traditional search. As of dash-improve-my-llms 2.3.3 the buckets are
# correct per vendor: ClaudeBot (Anthropic's *training* crawler) sits in the
# training block, while the user-triggered and search fetchers Claude-User /
# Claude-SearchBot are allowed alongside ChatGPT-User / OAI-SearchBot /
# PerplexityBot. With block_ai_training=False the training bucket is never
# emitted at all, which silently allows training — not "balanced".
app._robots_config = RobotsConfig(
    block_ai_training=True,       # Disallow GPTBot, ClaudeBot, CCBot, etc.
    allow_ai_search=True,         # Allow Claude-User/-SearchBot, ChatGPT-User, ...
    allow_traditional=True,       # Allow Googlebot, Bingbot, etc.
    crawl_delay=10,
    disallowed_paths=[],
)

# ============================================================================
# Register supplemental metadata for the home page.
# Markdown-driven pages register their own LLMS_DOC inside pages/markdown.py
# (the expanded markdown body becomes the literal /llms.txt response).
# ============================================================================

# `name` here is not a nav label — dash-improve-my-llms 2.3.4 resolves it into
# the /llms.txt H1 and the llms viewer's brand chip (`resolve_site_title`,
# home-page name first, `app.title` second, generic values skipped). It is the
# site's published identity, so it is SITE_BRAND and nothing else; the package
# name lives in the description. See lib/constants.py.
register_page_metadata(
    path="/",
    name=SITE_BRAND,
    description=SITE_DESCRIPTION,
    # The home page IS the package's entry in search, not an article about
    # one. Every other page defaults to TechArticle (pages/markdown.py).
    schema_type="SoftwareApplication",
    image_url=OG_IMAGE_URL,
)

# ============================================================================
# Site identity for the CRAWLER document (dash-improve-my-llms 2.5.0).
# Until 2.5.0 the generated crawler HTML carried the page's content signals
# and none of its identity: browsers got the icon links, og:image and twitter
# card from templates/index.html while Googlebot got zero of any of them, on
# every host in the network — so search showed the generic globe. One
# declaration covers every crawler surface, and it also claims /favicon.ico
# (Google's fallback), which Dash's page catch-all was answering with the app
# shell. Content may differ between the crawler document and the browser
# document; identity may not.
# ============================================================================
configure_seo(
    icons=[
        # Same paths templates/index.html links, so the two heads agree. The
        # .ico href is the assets/favicon/ copy (byte-identical to the root
        # one index.html links) so this list is SET-equal to what 2.6.0's
        # autodiscovery finds — tests/test_seo_icons.py pins that agreement.
        "/assets/favicon/favicon.ico",
        {"href": "/assets/favicon/favicon-32x32.png", "sizes": "32x32"},
        {"href": "/assets/favicon/favicon-16x16.png", "sizes": "16x16"},
        {"href": "/assets/favicon/favicon-96x96.png", "sizes": "96x96"},
        {"href": "/assets/favicon/android-chrome-192x192.png",
         "sizes": "192x192"},
        {"href": "/assets/favicon/android-chrome-512x512.png",
         "sizes": "512x512"},
        {"href": "/assets/favicon/apple-touch-icon.png",
         "rel": "apple-touch-icon", "sizes": "180x180"},
    ],
    social_image=OG_IMAGE_URL,
    social_image_alt=OG_IMAGE_ALT,
    social_image_width=OG_IMAGE_WIDTH,
    social_image_height=OG_IMAGE_HEIGHT,
    publisher=PUBLISHER,
    same_as=SAME_AS,
)

# Internal pages — excluded from /sitemap.xml, blocked in /robots.txt,
# skipped by the MCP bridge, and return 404 to crawler requests on the
# page URL and on /<page>/llms.txt. This boilerplate ships no internal pages,
# so there is nothing to hide; see docs/ai-integration for usage:
#
#     from dash_improve_my_llms import mark_hidden
#     mark_hidden("/admin")

# ============================================================================
# FastAPI showcase routes (only when running on FastAPI).
# These are NOT the AI/LLM endpoints — those are handled by add_llms_routes
# below. They are a small native API surface (`/healthz`, `/api/backend`,
# `/api/pages`) that demonstrates first-class OpenAPI/Swagger UI integration
# under Dash 4.1+'s FastAPI backend.
#
# Mounted BEFORE add_llms_routes so the package's catch-all
# `/<page>/llms.txt` matcher doesn't shadow these.
# ============================================================================

if BACKEND == "fastapi":
    from lib.asgi_routes import register_asgi_routes
    register_asgi_routes(app, BACKEND_INFO)
    print(
        "[boilerplate] FastAPI showcase routers mounted: /healthz, "
        "/api/backend, /api/pages. Swagger UI at /docs, ReDoc at /redoc."
    )
else:
    # Flask/Quart get the same /healthz the FastAPI build declares — the
    # 2plot.ai hub's hourly sweep probes it for the network health panel.
    from lib.health import register_health_route
    register_health_route(app, BACKEND)

# ============================================================================
# Analytics tracking (Flask / Quart) — MUST be registered BEFORE
# add_llms_routes.
#
# `before_request` hooks run in registration order, and the package's
# `_bot_middleware` short-circuits AI-search crawlers (ClaudeBot, ChatGPT-User,
# PerplexityBot, ...) with its own response. Registered after it, this hook
# never runs for exactly the bot traffic a docs site most wants counted, and
# the `bot_hits` we report to 2plot.ai would be quietly too low.
#
# FastAPI is the mirror image and is wired further down: Starlette runs the
# LAST-added middleware outermost, so ours goes on after add_llms_routes.
# ============================================================================

if IS_FLASK:
    from flask import request as _flask_request

    @app.server.before_request
    def track_visitor():
        """Track visitor analytics before each request."""
        try:
            # Headers are passed so the tracker can read the REAL client IP
            # and country from the proxy/CDN (behind Render or Cloudflare,
            # remote_addr is the proxy — every visitor would look like one).
            tracker.track_visit(
                _flask_request.path,
                _flask_request.headers.get('User-Agent', ''),
                _flask_request.remote_addr,
                headers=dict(_flask_request.headers),
            )
        except Exception:
            pass

elif BACKEND == "quart":
    from quart import request as _quart_request

    @app.server.before_request
    async def track_visitor():
        """Track visitor analytics before each request (Quart)."""
        try:
            tracker.track_visit(
                _quart_request.path,
                _quart_request.headers.get('User-Agent', ''),
                _quart_request.remote_addr,
                headers=dict(_quart_request.headers),
            )
        except Exception:
            pass

# Network bulletin — hub-published tips and announcements rendered in the
# header of the llms.txt view, so a twenty-site network says "here is what
# changed" once instead of in twenty repositories.
#
# This was commented out, with a note saying 2plot.dev did not serve
# /api/network/bulletin yet. The hub started serving it; the comment did not
# change; and NETWORK_BULLETIN_URL sat set in production against code that
# never read it. Nothing failed — the feature is opt-in, so an unwired app
# makes no request and the viewer header renders fine on the package's
# defaults. The only symptom was an announcement that never appeared.
#
# Hence lib/bulletin.py, and the boot line below: no commented-out wiring, and
# the log says which of the two states this process is in.
from lib import bulletin as _bulletin  # noqa: E402

BULLETIN_ENABLED = _bulletin.configure()
print(
    f"[boilerplate] network bulletin: {_bulletin.url()} "
    f"(app='{_bulletin.app_id()}')"
    if BULLETIN_ENABLED else
    "[boilerplate] network bulletin: off — set NETWORK_BULLETIN_URL="
    f"{_bulletin.HUB_BULLETIN_URL} to render the hub's announcements"
)

# ============================================================================
# Access control (dash-improve-my-llms 2.3). Reads the tiers the pages just
# declared, so it must run after they are registered and before the routes are
# attached. Stays OFF unless some page declares a non-public tier — the policy
# and the reasoning live in lib/access.py.
# ============================================================================

from lib import access as _access  # noqa: E402
from lib import page_tiers as _page_tiers  # noqa: E402
from lib import page_visibility as _page_visibility  # noqa: E402

# Tiered corpus documents (dash-improve-my-llms >= 2.4.0). Pseudo-paths: they
# never enter dash.page_registry, so they cannot leak into listings —
# registering them here lets this satellite tier its compact briefing and full
# corpus via env (LLMS_SMALL_TIER / LLMS_FULL_TIER), and the hub can tighten
# either network-wide through its page-tier ceilings with no redeploy here.
# The explicit `or "public"` matters: these registered under the
# PAGE_DEFAULT_TIER fallback before, which meant flipping that env to gate the
# *interactive* site would silently gate the corpus documents too. Their tier
# is now always a deliberate setting, never an ambient default.
_page_tiers.register("/llms-small.txt",
                     os.environ.get("LLMS_SMALL_TIER") or "public")
_page_tiers.register("/llms-full.txt",
                     os.environ.get("LLMS_FULL_TIER") or "public")

# The home page registers via pages/home.py, not pages/markdown.py, so no
# frontmatter ever declares its tier — under PAGE_DEFAULT_TIER=auth it would
# silently inherit the gate. The funnel's front door stays public, always.
_page_tiers.register("/", "public")

# The funnel's second step, pinned for the same reason as its first. Gating
# the page that teaches someone to `pip install dash-model-viewer` and put a
# model on screen would gate the only path to becoming a user — a docs site
# can gate its reference pages behind an account, but not its front door.
_page_tiers.register("/quick-start", "public")

# force= when either gate env is present: with every tier still public the
# auto-detect would skip the wiring, but a host that flips by env needs the
# verdict plumbing (and the prerender's use of it) live during the dark
# launch, not on the flip.
ACCESS_ENABLED = _access.configure(
    force=bool(os.environ.get("PAGE_DEFAULT_TIER")
               or os.environ.get("LLMS_PUBLIC_DEFAULT"))
)

# Wire up the package: /llms.txt, /<page>/llms.txt, /robots.txt, /sitemap.xml,
# bot-detection middleware, and (on Dash 4.3+) MCP resource registration.
# Works under Flask, FastAPI, and Quart — no gating needed.
#
# /<page>/llms.txt content-negotiates from 2.2.0 on: agents and crawlers get
# the Markdown byte for byte, browsers get it rendered behind the network
# header. `?raw=1` and `?format=html` force either side, and both variants
# send `Vary: Accept` so a CDN cannot hand cached HTML to the next agent.
add_llms_routes(app, LLMSConfig(warn_missing_llms_doc=True))

# ============================================================================

app.layout = create_appshell(dash.page_registry.values())

server = app.server

# ============================================================================
# The person→agent handoff: /api/agent-key turns the browser's Clerk session
# into a portable ?key= for copied llms.txt URLs (lib/agent_key.py). 204 for
# everyone until Clerk and the hub are configured — safe to mount always.
# ============================================================================

from lib.agent_key import register_agent_key_route  # noqa: E402

register_agent_key_route(app, BACKEND)

_non_public = sum(1 for t in _page_tiers.registered().values() if t != "public")
print(
    f"[boilerplate/modelviewer] interactive gate: default tier "
    f"'{os.environ.get('PAGE_DEFAULT_TIER') or 'public'}', "
    f"{_non_public} non-public page(s), machine surfaces "
    f"{'GATED' if not _page_tiers.get_llms_public('/__probe__') else 'open'} "
    f"by default (LLMS_PUBLIC_DEFAULT), access wiring "
    f"{'ON' if ACCESS_ENABLED else 'off'}, control board at "
    f"/admin/control-board ({_page_visibility.override_count()} live "
    f"override(s))."
)

# ============================================================================
# Analytics Tracking (FastAPI) — added LAST on purpose.
# Starlette runs the most recently added middleware outermost, so registering
# here (after add_llms_routes) puts the tracker in front of the package's bot
# middleware and every request gets counted. The Flask/Quart hooks are the
# mirror image and live above.
# ============================================================================

if BACKEND == "fastapi":
    from lib.asgi_middleware import register_asgi_middleware

    register_asgi_middleware(app)

# ============================================================================
# Network analytics — hourly signed rollup POSTed to 2plot.ai so the hub's
# owner-only /traffic dashboard can chart this app alongside the network.
# Contract: 2plotai/docs/network/satellite-analytics.md.
# No-op unless CROSS_APP_WEBHOOK_SECRET is set.
# ============================================================================

from lib.satellite_reporter import start_reporter

start_reporter()

# MCP wiring used to live down here, calling `from dash import mcp_enabled`
# and `mcp_enabled(app)`. Both were wrong: the symbol lives in `dash.mcp`, not
# `dash`, so the import always raised ImportError and the app printed
# "MCP not available in dash 4.4.1 (needs >=4.3)" — while running 4.4.1. And
# `mcp_enabled` is the decorator that marks a *function* as an MCP tool, not a
# server switch. The server is started from Dash's constructor, so the real
# wiring is `enable_mcp=` at the top of this file.

# ============================================================================


if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port='8559')
