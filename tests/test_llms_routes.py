"""The AI/LLM and SEO surfaces: llms.txt, sitemap.xml, robots.txt, canonicals."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import pytest

from conftest import BROWSER_ACCEPT, CRAWLER_UA
from lib import network_directory as nd
from lib.constants import BASE_URL

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def test_root_llms_txt_is_an_index(client):
    body = client.get("/llms.txt").text
    assert "# " in body, "llms.txt should open with a heading"
    assert "## Network" in body, "the cross-host directory is missing from llms.txt"


def test_every_page_has_its_own_llms_txt(client, page_paths):
    failures = []
    for path in page_paths:
        url = "/llms.txt" if path == "/" else f"{path.rstrip('/')}/llms.txt"
        response = client.get(url)
        if not response.ok or len(response.text) < 200:
            failures.append((url, response.status, len(response.text)))
    assert failures == [], f"per-page llms.txt missing or empty: {failures}"


def test_page_llms_txt_carries_the_page_prose(client):
    body = client.get("/quick-start/llms.txt").text
    assert "Your first viewer" in body
    assert "vendored" in body, "page prose did not reach /<page>/llms.txt"


def test_source_directives_are_expanded_in_llms_txt(client):
    """`.. source::` must inline the referenced file, not name it.

    The audience for /<page>/llms.txt is someone pasting it into a chat
    window; a directive reference is useless to them.
    """
    body = client.get("/quick-start/llms.txt").text
    assert ".. source::" not in body, "an unexpanded directive leaked into the prose"
    assert "component = html.Div(" in body, "the referenced source file was not inlined"


def test_robots_txt(client):
    body = client.get("/robots.txt").text
    assert "User-agent:" in body
    assert f"Sitemap: {BASE_URL}/sitemap.xml" in body, "robots.txt must point at this host's sitemap"


def test_robots_artifact_fingerprint(client):
    """The robots.txt crawler split is the network's proof-of-artifact.

    pip metadata is invisible from outside, so these exact robots.txt pairs
    are how a live host is fingerprinted as running the intended
    dash-improve-my-llms — the post-deploy check on every host in the
    rollout. If this fails locally, the installed package regressed.

    The signature, by release that introduced it:

    - 2.3.2: `OAI-SearchBot -> Allow` (ChatGPT search's crawler; pre-fix
      builds disallowed it).
    - 2.3.3: `ClaudeBot -> Disallow` (the actual *training* crawler, moved to
      the training bucket) while `Claude-User` and `Claude-SearchBot` — the
      user-triggered and search fetchers — are allowed.
    """
    lines = client.get("/robots.txt").text.splitlines()

    def rule(agent):
        idx = lines.index(f"User-agent: {agent}")
        return lines[idx + 1]

    assert rule("OAI-SearchBot") == "Allow: /", "pre-2.3.2 artifact"
    assert rule("ClaudeBot") == "Disallow: /", "pre-2.3.3 artifact"
    assert rule("Claude-User") == "Allow: /", "pre-2.3.3 artifact"
    assert rule("Claude-SearchBot") == "Allow: /", "pre-2.3.3 artifact"


def test_sitemap_lists_every_page_on_this_host(client, page_paths):
    body = client.get("/sitemap.xml").text
    root = ET.fromstring(body)
    locs = [el.text for el in root.findall(".//sm:url/sm:loc", SITEMAP_NS)]
    assert locs, "sitemap.xml contains no <url> entries"

    foreign = [loc for loc in locs if urlparse(loc).netloc != urlparse(BASE_URL).netloc]
    assert foreign == [], f"sitemap.xml lists URLs on another host: {foreign}"

    listed = {urlparse(loc).path.rstrip("/") or "/" for loc in locs}
    missing = {p.rstrip("/") or "/" for p in page_paths} - listed
    assert not missing, f"pages absent from sitemap.xml: {sorted(missing)}"


def test_canonical_points_at_this_host_and_path(client, page_paths):
    """The failure mode that deindexed a satellite for months.

    A canonical on the wrong host tells Google the page is a duplicate of
    somewhere else. Checked per page, because a template-level canonical is
    right on the home page and wrong everywhere else.
    """
    wrong = []
    for path in page_paths:
        html = client.get(path, user_agent=CRAWLER_UA).text
        found = re.findall(r'rel="canonical"\s+href="([^"]*)"', html)
        expected = f"{BASE_URL}{path}"
        if found != [expected]:
            wrong.append((path, found))
    assert wrong == [], f"bad canonical tags (expected exactly one, this host): {wrong}"


def test_exactly_one_canonical_tag_for_browsers(client):
    """A hard-coded canonical in index.html doesn't replace the injected one.

    It joins it, and two conflicting canonicals are read as no signal at all.

    Counts ELEMENTS, not the bare substring `rel="canonical"`. The template
    both explains itself in comments and now ships a script whose selector
    names the attribute (`link[rel="canonical"]`, the SPA URL sync) — neither
    is a canonical tag, and a substring count read both as one. Same lesson as
    the `dv-banner` chrome check below: match the markup, not the words, so a
    file may legitimately discuss what it is being checked for.
    """
    html = re.sub(r"<!--.*?-->", "", client.get("/quick-start").text, flags=re.S)
    tags = re.findall(r'<link[^>]+rel="canonical"[^>]*>', html)
    assert len(tags) == 1, f"expected exactly one canonical element, got {tags}"


def test_healthz(client):
    """The 2plot.ai hub probes this hourly on every backend."""
    response = client.get("/healthz")
    assert response.ok
    assert "ok" in response.text.lower()


# ---------------------------------------------------------------------------
# Content negotiation on /<page>/llms.txt (dash-improve-my-llms 2.2.0)
#
# One URL, two audiences. Agents must get Markdown byte for byte; people who
# paste the URL into a browser get it rendered. The failure mode this guards
# against is subtle in both directions: viewer chrome leaking into the
# Markdown makes every agent in the network pay tokens for decoration and
# shows up in no dashboard, and a CDN that ignores `Vary` can hand a cached
# HTML response to the next agent that asks.
# ---------------------------------------------------------------------------

# Deliberately not /networks/llms.txt: that page *documents* the viewer, so its
# prose contains the words "dv-banner" and "mk-wordmark" legitimately.
PAGE_DOC = "/api-reference/llms.txt"

# Chrome is detected as rendered markup rather than as a bare class name. A
# Markdown document may legitimately discuss `dv-banner`; it can never contain
# `<div class="dv-banner">`. Keying on the token instead makes any page that
# writes about the viewer fail, which teaches people to stop writing about it.
CHROME = re.compile(r'<[a-z]+ class="dv-banner')


def test_agents_get_markdown(client):
    response = client.get(PAGE_DOC)
    assert response.ok
    assert "text/markdown" in response.content_type, response.content_type
    assert not CHROME.search(response.text), "viewer chrome leaked into the agent's copy"
    assert "<!DOCTYPE html>" not in response.text


def test_browsers_get_the_rendered_view(client):
    response = client.get(PAGE_DOC, accept=BROWSER_ACCEPT)
    assert response.ok
    assert "text/html" in response.content_type, response.content_type
    assert CHROME.search(response.text), "the viewer header is missing"
    assert "mk-wordmark" in response.text, "the network wordmark is missing"


def test_the_banner_renders_its_panels_without_a_bulletin(client):
    """Tips and What's new appear with the package's built-in defaults.

    `configure_bulletin()` is deliberately unwired here — 2plot.dev doesn't
    serve the endpoint yet — and this pins the fact that the header is fully
    formed regardless. Without it, "the banner looks wrong" could mean either
    a missing bulletin or a broken viewer, and those have very different
    fixes.
    """
    html = client.get(PAGE_DOC, accept=BROWSER_ACCEPT).text
    assert "Tips for getting started" in html
    assert "Append /llms.txt to any page URL" in html, "the default tip is missing"
    assert "What's new" in html
    assert "No announcements." in html, "the empty-state text is missing"


def test_the_banner_carries_this_app_and_network_identity(client):
    """The banner must name *this* site, not the package's demo app."""
    html = client.get(PAGE_DOC, accept=BROWSER_ACCEPT).text
    assert nd.NETWORK_NAME in html, "the banner does not name the network"
    assert nd.HUB_URL in html, "the banner does not link the hub"


@pytest.mark.skip(
    reason="No page on this site documents the llms viewer's chrome, so there "
    "is no prose here that legitimately contains `dv-banner`. The guard it "
    "pins (CHROME must not be substring-based) is still exercised by "
    "test_agents_get_markdown. Restore this if a page ever quotes the viewer's "
    "markup — do NOT satisfy it by adding the string to a page."
)
def test_a_page_may_document_the_viewer_without_tripping_the_check(client):
    """A page whose prose names `dv-banner` is content, not chrome."""
    response = client.get("/quick-start/llms.txt")
    assert "text/markdown" in response.content_type
    assert "dv-banner" in response.text, "expected the page to discuss the class name"
    assert not CHROME.search(response.text), "that mention must not read as chrome"


def test_crawlers_get_markdown_not_the_viewer(client):
    """Googlebot asks for HTML by habit. It still gets the document.

    The rendered view is `noindex` precisely so it never competes with the
    real page, so serving it to a crawler would waste the fetch.
    """
    response = client.get(PAGE_DOC, user_agent=CRAWLER_UA)
    assert "text/markdown" in response.content_type, response.content_type


def test_both_variants_send_vary_accept(client):
    """Without `Vary: Accept`, a shared cache serves whichever variant it saw
    first to everyone — including HTML to an agent."""
    for accept in (None, BROWSER_ACCEPT):
        response = client.get(PAGE_DOC, accept=accept)
        assert "accept" in response.header("Vary").lower(), (
            f"Vary is {response.header('Vary')!r} for Accept={accept!r}"
        )


def test_query_overrides_beat_the_accept_header(client):
    """`?raw=1` for a person debugging in a browser, `?format=html` for a
    person sharing a link from a terminal."""
    raw = client.get(f"{PAGE_DOC}?raw=1", accept=BROWSER_ACCEPT)
    assert "text/markdown" in raw.content_type, raw.content_type

    rendered = client.get(f"{PAGE_DOC}?format=html")
    assert "text/html" in rendered.content_type, rendered.content_type


def test_the_rendered_view_is_noindex(client):
    """It is the same content as the page it documents. Indexed, it would
    compete with it."""
    response = client.get(PAGE_DOC, accept=BROWSER_ACCEPT)
    assert re.search(r'<meta[^>]+name="robots"[^>]+noindex', response.text), (
        "the viewer must not be indexable"
    )


# ---------------------------------------------------------------------------
# The navigation block (2.2.0)
#
# A page's llms.txt is usually read in isolation — pasted into a chat, handed
# to an agent. Before 2.2.0 it was a dead end: it described one page and gave
# an agent nothing to follow.
# ---------------------------------------------------------------------------


def test_page_documents_are_not_dead_ends(client):
    body = client.get(PAGE_DOC).text
    assert f"{BASE_URL}/llms.txt" in body, "no route back to this site's index"
    assert f"{BASE_URL}/sitemap.xml" in body, "no sitemap link"


def test_nav_block_points_one_level_up_the_hub_chain(client):
    """A subdomain names its section hub, not the network root.

    Each llms.txt then has exactly one "up" link and an agent walks the chain.
    This app is a `*.2plot.dev` subdomain, so its hub is 2plot.dev.
    """
    body = client.get(PAGE_DOC).text
    assert f"{nd.HUB_URL}/llms.txt" in body, f"expected the hub chain to reach {nd.HUB_URL}"


def test_nav_block_is_absent_from_the_root_index(client):
    """The root document *is* the site index; pointing it at itself is noise."""
    body = client.get("/llms.txt").text
    assert "## Pages" in body, "the root document should be an index"
    assert not CHROME.search(body), "viewer chrome leaked into the root index"
