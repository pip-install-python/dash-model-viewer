"""Every page loads, and every page serves real content to a crawler."""

from __future__ import annotations

import re

import pytest

from conftest import CRAWLER_UA, STUB_MARKER, main_body

# Pages that must exist. A markdown file silently failing to register is
# invisible in a smoke test that only iterates whatever did register — the
# suite would pass with half the site missing.
REQUIRED_PATHS = {
    "/",
    "/quick-start",
    "/events-and-callbacks",
    "/camera-and-views",
    "/slots-and-hotspots",
    "/attributes-and-parity",
    "/augmented-reality",
    "/model-switching",
    "/api-reference",
    "/migrating",
    "/scene-director",
    "/generative-3d",
    "/image-to-3d",
    "/benchmark",
}


def test_every_required_page_registered(page_paths):
    missing = REQUIRED_PATHS - set(page_paths)
    assert not missing, f"pages missing from dash.page_registry: {sorted(missing)}"


def test_no_duplicate_page_paths(page_paths):
    duplicates = {p for p in page_paths if page_paths.count(p) > 1}
    assert not duplicates, f"two pages registered on the same path: {sorted(duplicates)}"


def test_pages_are_reachable(client, page_paths):
    failures = [(p, client.get(p).status) for p in page_paths]
    assert [f for f in failures if f[1] != 200] == []


def test_no_page_serves_the_javascript_stub(client, page_paths):
    """The regression that cost this network twelve of fourteen crawlable URLs.

    A stub here means the page has no prose registered, or something erased
    it after registration. Either way crawlers and agents see nothing.
    """
    stubbed = [p for p in page_paths if STUB_MARKER in client.get(p, user_agent=CRAWLER_UA).text]
    assert stubbed == [], f"pages serving the stub body to crawlers: {stubbed}"


def test_crawler_bodies_are_substantial(client, page_paths):
    """A page can avoid the stub and still serve almost nothing."""
    thin = []
    for path in page_paths:
        body = main_body(client.get(path, user_agent=CRAWLER_UA).text)
        if len(body) < 2000:
            thin.append((path, len(body)))
    assert thin == [], f"suspiciously small crawler bodies: {thin}"


def test_prose_renders_as_html_not_literal_markdown(client):
    """2.1's renderer: links, code fences, rules and tables, not raw text.

    Before 2.1 these came through as `<p>---</p>`, literal `[text](url)` and
    pipe characters. Checked on /slots-and-hotspots because it carries the most
    code fences of any page here (5, measured) — the threshold below is that
    count minus a little headroom, not a number copied from another repo.
    """
    body = main_body(client.get("/slots-and-hotspots", user_agent=CRAWLER_UA).text)

    assert body.count("<pre") >= 4, "expected code fences to render as <pre> blocks"
    assert "<hr" in body, "expected horizontal rules to render as <hr>"
    assert not re.search(r"<p>\s*-{3,}\s*</p>", body), "horizontal rule leaked as literal text"
    assert not re.search(r"\[[^\]]+\]\(https?://", body), "markdown link leaked as literal text"


def test_pages_have_distinct_titles(client, page_paths):
    """Dash serves one static index template for every route, so without a
    per-page title every URL ships identical head metadata — which is most of
    what makes a site look like a set of near-duplicates."""
    titles = {}
    for path in page_paths:
        html = client.get(path).text
        match = re.search(r"<title>(.*?)</title>", html, re.S)
        assert match, f"{path} served no title element"
        titles[path] = match.group(1).strip()

    duplicates = {t for t in titles.values() if list(titles.values()).count(t) > 1}
    assert not duplicates, f"pages sharing a title: {duplicates}"


def test_home_page_links_out_to_other_pages(client):
    body = main_body(client.get("/", user_agent=CRAWLER_UA).text)
    assert body.count("<a href=") >= 5, "home page prose has almost no outbound links"


@pytest.mark.parametrize("path", ["/nope", "/quick-start/does-not-exist"])
def test_unknown_paths_do_not_500(client, path):
    assert client.get(path).status in (200, 404), "unknown path should 404 or render the app's 404"


def test_prerender_rides_the_generic_lane_not_a_ua_gate(client):
    """The universal prerender must be in the initial HTML for a PLAIN
    client — no crawler user-agent. An outside SEO audit (2026-08-22) read
    five hosts as serving "Loading... and nothing else" to browsers; the
    prose was there all along, but every test in this file fetched with
    CRAWLER_UA (which exercises the separate bot-document path), so a
    regression that UA-gated the universal lane would have been invisible
    to the suite. This test is the generic-lane pin.

    Since the 2.6.1 floor the block must also be VISIBLE: dimll <= 2.6.0
    shipped the div with a literal `hidden` attribute, so every
    visibility-respecting text extractor (and arguably crawler
    content-weighting) saw only "Loading..." — present and invisible, the
    worst of both. 2.6.1 serves it visible and hides it via a synchronous
    inline script that only JS browsers execute (React's mount then wipes
    the pair, so nothing changes for humans). The div shape below is the
    regression pin for that fix, from the app's side.
    """
    for path in ("/", "/quick-start"):
        html = client.get(path).text  # default UA — the point of the test
        div = re.search(r'<div id="dimll-prerender"[^>]*>', html)
        assert div, (
            f"{path}: no prerender block for a generic client — the "
            "universal lane is gated or off"
        )
        assert "hidden" not in div.group(0), (
            f"{path}: the prerender div carries `hidden` again — "
            "visibility-respecting consumers are back to reading "
            "'Loading...'; the floor first moved (to 2.6.1) for exactly "
            "this, and sits at >=2.8.0 now"
        )
        assert 'data-dimll-prerender="1">document.getElementById' in html, (
            f"{path}: the marked synchronous hide script is missing — "
            "JS browsers would flash the prose before React mounts"
        )
        assert "<main>" in html, f"{path}: prerender block carries no <main> prose"


def test_prerender_single_h1_and_deduped_footer_llms_links(client, page_paths):
    """What the >=2.7.1 floor buys, pinned from the app's side, EVERY page.

    Below dimll 2.7.0 every page served TWO h1s to a generic client — the
    injected prerender header plus the doc body's own markdown H1, a
    duplicate-H1 page in every crawler's eyes (2026-08-22 SEO-audit
    finding) — and the home footer printed its /llms.txt link twice (on
    "/" the per-page link equals the root's; subpages legitimately carry
    both, DISTINCT). The sweep also catches app-side H1 pollution: the
    first run of this test found docs/example's machine lane serving FIVE
    h1s because _expand_source_directives expanded a `.. source::` example
    inside a ```markdown teaching fence (fixed fence-aware, 1.6.11).

    HTML comments are stripped before counting: templates/index.html
    legitimately SAYS "<h1>" inside the comment explaining its noscript
    block. Admin pages are skipped — they are hidden from machine
    surfaces and carry no prerender.
    """
    for path in page_paths:
        if path.startswith("/admin"):
            continue
        html = client.get(path).text  # default UA — the universal lane
        stripped = re.sub(r"<!--.*?-->", "", html, flags=re.S)

        h1s = re.findall(r"<h1[\s>]", stripped)
        assert len(h1s) == 1, (
            f"{path}: {len(h1s)} h1 elements in the generic-lane document — "
            "either the pre-2.7.0 prerender-header duplicate or app-side "
            "markdown leaking headings (the fence-expansion class)"
        )

        footer = re.search(r"<footer.*?</footer>", stripped, re.S)
        assert footer, f"{path}: no prerender footer in the generic-lane document"
        llms_links = re.findall(r'href="([^"]*llms\.txt)"', footer.group(0))
        assert len(llms_links) == len(set(llms_links)), (
            f"{path}: duplicate llms.txt links in the prerender footer "
            f"({llms_links}) — 2.7.0 dedups the per-page link when it "
            "equals the root"
        )
        if path == "/":
            assert llms_links == ["/llms.txt"], (
                f"home footer llms links {llms_links} — expected exactly the "
                "root link once"
            )


def test_source_expansion_is_fence_aware(app):
    """A `.. source::` inside a fenced block is documentation, not a directive.

    The template's docs/example and docs/directives TEACH the directive
    inside ```markdown fences. No page in THIS repo does yet, so the
    defect is latent here rather than live — which is exactly when a pin
    is cheapest to install. Expanding those injects a ```python fence inside
    the already-open fence, which closes it early — from there the inlined
    file renders as markdown on the machine lane and every `# comment`
    line becomes an <h1> (the five-h1 finding, 2026-08-23). The app
    fixture is requested only so pages/markdown.py is already imported
    with the repo root as CWD.
    """
    import sys

    expand = sys.modules["pages.markdown"]._expand_source_directives

    expanded = expand(".. source::requirements.txt")
    assert "# File: requirements.txt" in expanded, "real directive not expanded"
    assert "```" in expanded, "expansion lost its fence"

    taught = "```markdown\n.. source::requirements.txt\n```"
    assert expand(taught) == taught, "a fenced example was expanded"

    tilde = "~~~\n.. source::requirements.txt\n~~~"
    assert expand(tilde) == tilde, "a tilde-fenced example was expanded"
