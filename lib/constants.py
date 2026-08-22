import os

# ---------------------------------------------------------------------------
# Site identity — one string, every surface
# ---------------------------------------------------------------------------
# The network standard (2plot.ai and 2plot.dev both ship it): a site states
# what it is, in the same words, on every surface an agent or a reader can
# reach. The surfaces this brand has to reach, and what serves each:
#
#   Dash(title=SITE_BRAND)              -> <title>, and the fallback identity
#   register_page_metadata(path="/",    -> the /llms.txt H1 and the llms
#       name=SITE_BRAND)                   viewer's brand chip, both via
#                                          dash-improve-my-llms 2.3.4's
#                                          `resolve_site_title`
#   pages/home.md's opening `# ` line   -> the home page's own prose
#
# tests/test_site_identity.py pins all four to this constant, because the
# failure is silent: `resolve_site_title` skips generic candidates ("Home",
# "Index", Dash's default "Dash"), so a site that never states its identity
# publishes a nav label or a framework default and nothing looks broken. That
# is exactly what this host did before — the viewer chip read a bare "Dash".
#
# Naming rules, from the network standard:
#   - the PACKAGE NAME belongs in the description, not in the brand;
#   - "Pip Install Python" is the byline (who made it), never the site name.
SITE_BRAND = "dash-model-viewer — interactive 3D models and AR for Dash"

# 149 characters, and the ceiling is the point: this string becomes the
# `<meta name="description">`, og:description and twitter:description via
# `register_page(description=)`, and Google truncates those around 155. The
# previous version ran to 360 — so the half that actually said what makes this
# package different ("works offline", "no CDN") was cut off in every search
# result and every social preview, which is the half worth keeping.
#
# The long prose did not go anywhere: it belongs in the home page body, the
# README and /llms.txt, none of which are length-penalised. A tagline is not a
# summary. tests/test_site_identity.py pins the ceiling.
SITE_DESCRIPTION = (
    "dash-model-viewer — interactive 3D models and AR for Dash. Google's "
    "model-viewer vendored in the wheel: no CDN, works offline. "
    "By Pip Install Python."
)

# Resolves {%title%} in templates/index.html, which is what the served HTML
# carries when dash-improve-my-llms is not rewriting the title per page
# (LLMSConfig(prerender=False), the documented rollback). Per-page titles still
# come from PAGE_TITLE_PREFIX below.
APP_TITLE = SITE_BRAND

# The brand without its tagline. SITE_BRAND is right for a page that has room
# for it; this is for the places that prefix something else and would otherwise
# run past every platform's truncation point.
SITE_SHORT_NAME = "dash-model-viewer"

# Prefixed to every per-page title (`pages/markdown.py`, `pages/home.py`), and
# therefore NOT only a browser-tab string: Dash passes the page title straight
# into `og:title` and `twitter:title` (dash/_pages.py `_page_meta_tags`), so
# this is the headline on every share card the site produces.
#
# It read "Dash Pip Components | " until 1.2.2 — the fork source's brand,
# inherited and never changed, so every unfurl of boilerplate.2plot.dev
# advertised a different site while `<title>`, `og:site_name` and the
# /llms.txt H1 all correctly said this one. That is exactly the drift the
# network's identity rule exists to stop, and it is invisible from inside the
# app because nobody sees their own share cards.
#
# Network convention, matching the other satellites (`dash-leaflet2 | `,
# `Dash Email | `): the SHORT site name, then a pipe. Derived rather than
# retyped so the two cannot drift apart; tests/test_site_identity.py pins the
# relationship.
PAGE_TITLE_PREFIX = f"{SITE_SHORT_NAME} | "

PRIMARY_COLOR = "indigo"
# Tracks the *package* version this site documents, not a site version —
# there is one artifact here and two audiences for it.
APP_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# The network's internal-traffic contract
# ---------------------------------------------------------------------------
# The analytics point of truth is https://2plot.ai/docs/satellite-analytics
# ("Internal traffic"): any request whose User-Agent contains
# INTERNAL_UA_TOKEN is 2plot network machinery talking to itself — the hub's
# hourly health sweep, CI smoke batteries, the 4x-daily heartbeat, this app's
# own server-to-server calls to the hub. It is counted NOWHERE.
#
# Two halves, and both are required for the contract to hold:
#
#   inbound  — every tracker drops a token-carrying request at WRITE time,
#              before device detection and before bot classification, so it
#              never reaches the ledger the hourly rollup is built from;
#   outbound — every call this host makes to another network host sends
#              INTERNAL_UA, so the far side can apply the same rule.
#
# The outbound half is the one that was missing here. lib/ad_client.py fetched
# campaigns from 2plot.dev as bare `python-requests`, which the hub's own
# tracker classifies as a bot — every page view on this satellite was inflating
# 2plot.dev's bot_hits. lib/satellite_reporter.py and lib/hub_client.py had the
# same shape.
#
# The token string must stay byte-identical across the network; it mirrors
# 2plotai/lib/constants.py and pip-docs+/lib/constants.py.
INTERNAL_UA_TOKEN = "2plot-internal"
INTERNAL_UA = "2plot-internal/1.0 (+https://2plot.ai/docs/satellite-analytics)"


def internal_ua(caller: str = "") -> str:
    """``INTERNAL_UA`` with a caller suffix, e.g. ``"ad-client"``.

    The suffix is for reading logs on the far side; only the token matters to
    the contract, and it stays intact whatever the suffix says.
    """
    caller = (caller or "").strip()
    return f"{INTERNAL_UA} {caller}" if caller else INTERNAL_UA


# ---------------------------------------------------------------------------
# Public origin
# ---------------------------------------------------------------------------
# BASE_URL drives <link rel="canonical"> on every page, the absolute URLs in
# sitemap.xml, and the "this app" entry in /llms.txt. It is the single
# highest-consequence value in the template.
#
# THE FOOTGUN: this repo is the template the satellite documentation sites are
# forked from. A satellite that forks it and never changes this value emits
#     <link rel="canonical" href="https://boilerplate.2plot.dev/...">
# on every one of its pages — which tells Google that the entire satellite is
# a duplicate of the boilerplate and asks for it to be dropped from the index.
# Traffic disappears and nothing in the app looks broken.
#
# So: override APP_BASE_URL per deployment. `require_owned_base_url()` below
# refuses to boot in production if you didn't.
DEFAULT_BASE_URL = "https://modelviewer.2plot.dev"
BASE_URL = os.environ.get("APP_BASE_URL", DEFAULT_BASE_URL).rstrip("/")

# ---------------------------------------------------------------------------
# The social card
# ---------------------------------------------------------------------------
# TEMPLATE VALUE: a fork points this at its own image and changes nothing else.
#
# Dash builds `og:image` and `twitter:image` for every page (dash/_pages.py).
# When no `image_url=` is passed it INFERS one from the assets folder, looking
# for `<page>.<ext>`, then `app.<ext>`, then `logo.<ext>` — and this repo ships
# `assets/logo.svg`, so it inferred that. Two separate failures followed, both
# invisible from inside the app:
#
#   1. SVG is not a valid social image. Facebook, Twitter/X, LinkedIn and
#      Slack all reject it, so the card fell back to no image at all;
#   2. it DUPLICATED the og:image already declared in templates/index.html.
#      Two tags, and the scraper picks — usually the last, which was the SVG.
#
# Passing an explicit absolute `image_url` at register_page time resolves both:
# it overrides the inference, and it lets index.html stop declaring the URL
# itself and keep only the auxiliary width/height/alt tags Dash never emits.
#
# THE CARD LIVES ON THE CDN, NOT IN assets/. Network rule, and it is about
# cold starts rather than tidiness: a card served by the app is fetched by the
# scraper at unfurl time, and on a cold free-tier container that request lands
# mid-wake and times out. The preview renders blank ONCE and the platform
# caches the miss — so the first person to share the link poisons it for
# everyone. The CDN has no cold start.
#
# Rendered by `scripts/make_social_card.py` (1200x630 = 1.91:1, the Open Graph
# ideal, which also degrades cleanly into Twitter's 2:1 slot) and uploaded by
# hand to the Cloudflare bucket. There is no automated path to that bucket.
#
# Until 1.2.3 this was `{BASE_URL}/assets/ddb.png` — the app-served 784x741
# logo. Honest dimensions, but near-square: `summary_large_image` letterboxed
# it into a wide slot with bars either side.
#
# The width and height MUST match the file. A declared size that disagrees is
# worse than declaring none, because the platform reserves that box and crops
# into it. `tests/test_social_card.py` pins these against
# `templates/index.html`, and `scripts/smoke_live.py` fetches the real file
# after every deploy and checks its actual pixels against them — the only
# check that can catch the CDN object being replaced with something a
# different shape.
OG_IMAGE_URL = "https://cdn.2plot.ai/github_assets/modelviewer.2plot.dev.png"
OG_IMAGE_WIDTH = 1200
OG_IMAGE_HEIGHT = 630
OG_IMAGE_TYPE = "image/png"
OG_IMAGE_ALT = SITE_BRAND

# The package cross-link block — who publishes this site, and which other URLs
# are the same entity. `SAME_AS` becomes JSON-LD `sameAs` on every crawler
# page: for a docs satellite it should list the documented package's GitHub
# repo and PyPI project, because three properties pointing at each other is the
# strongest statement of which URL is a package's canonical docs home. The
# other half of the loop — PyPI `project_urls` and the GitHub README pointing
# back at this subdomain — is a per-package checklist item, not code, and
# pyproject.toml already holds up its end.
PUBLISHER = "Pip Install Python LLC"
SAME_AS = [
    "https://github.com/pip-install-python/dash-model-viewer",
    "https://pypi.org/project/dash-model-viewer/",
]


def require_owned_base_url(base_url: str = BASE_URL) -> None:
    """Fail fast in production when BASE_URL isn't this app's real origin.

    Only enforced when a hosting platform is detected (Render sets ``RENDER``;
    ``APP_ENV=production`` works anywhere else), so local development and the
    test suite are unaffected.

    Two failures are caught:

    1. **APP_BASE_URL unset in production.** A fork inherits the boilerplate's
       default and quietly deindexes itself. There is no safe guess to make on
       its behalf, so this raises.
    2. **A platform-generated hostname.** ``*.onrender.com`` /
       ``*.herokuapp.com`` still resolve after a custom domain is attached, so
       canonicals pointing there split link equity across two hostnames for as
       long as nobody notices.
    """
    in_production = bool(os.environ.get("RENDER") or os.environ.get("APP_ENV") == "production")
    if not in_production:
        return

    if not os.environ.get("APP_BASE_URL"):
        raise RuntimeError(
            "APP_BASE_URL is not set. This app would serve "
            f"<link rel='canonical' href='{DEFAULT_BASE_URL}'> on every page, "
            "telling search engines it is a duplicate of the documentation "
            "boilerplate. Set APP_BASE_URL to this deployment's real origin "
            "(e.g. https://leaflet.2plot.dev)."
        )

    for platform_host in ("onrender.com", "herokuapp.com", "railway.app", "fly.dev"):
        if platform_host in base_url:
            raise RuntimeError(
                f"APP_BASE_URL={base_url!r} is a platform-generated hostname. "
                "Canonical tags, sitemap.xml and llms.txt would all point at it "
                "instead of the custom domain, splitting link equity across two "
                "hosts. Set APP_BASE_URL to the public domain."
            )


# Height of the fixed AppShell header, in px. Consumed by AppShell(header=...)
# and by the mobile drawer, which docks itself directly below the header.
# Change it here only — the two must never drift apart.
HEADER_HEIGHT = 70

# This will be populated by pages/markdown.py when loading documentation files
NAME_CONTENT_MAP = {}
PROPS_TO_EXCLUDE = [
    "unstyled",
    "m",
    "my",
    "mx",
    "mt",
    "mb",
    "ms",
    "me",
    "ml",
    "mr",
    "p",
    "py",
    "px",
    "pt",
    "pb",
    "ps",
    "pe",
    "pl",
    "pr",
    "bg",
    "c",
    "opacity",
    "ff",
    "fz",
    "fw",
    "lts",
    "ta",
    "lh",
    "fs",
    "tt",
    "td",
    "w",
    "miw",
    "maw",
    "h",
    "mih",
    "mah",
    "bgsz",
    "bgp",
    "bgr",
    "bga",
    "pos",
    "top",
    "left",
    "bottom",
    "right",
    "inset",
    "display",
    "flex",
]
