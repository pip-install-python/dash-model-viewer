"""Site identity: one brand, every surface, verbatim.

The network standard says a site states what it is in the same words
everywhere an agent or a reader can reach. The failure this pins is silent,
which is why it needs tests rather than a code review: nothing errors when a
surface falls back to a default. On this host, before `SITE_BRAND` existed,
the llms viewer's brand chip read a bare **"Dash"** — the `Dash()`
constructor's default title, leaking out as the public identity of a
production documentation site.

dash-improve-my-llms 2.3.4's `resolve_site_title` is what makes the fix
possible: it takes the home page's registered `name` first, `app.title`
second, and *skips* generic candidates ("Home", "Index", "Dash") rather than
publishing them. These tests assert both ends of that — the inputs this repo
controls, and the H1 it produces.
"""

from __future__ import annotations

import re
from pathlib import Path

from conftest import REPO_ROOT
from lib.constants import (
    PAGE_TITLE_PREFIX,
    SITE_BRAND,
    SITE_DESCRIPTION,
    SITE_SHORT_NAME,
)

# Spelled out rather than imported, so that renaming the constant cannot
# silently rename the site. Changing the brand should require changing this
# line, deliberately.
EXPECTED_BRAND = "dash-model-viewer — interactive 3D models and AR for Dash"


def test_brand_constant_is_the_agreed_identity():
    assert SITE_BRAND == EXPECTED_BRAND


def test_app_title_is_the_brand(app):
    """`Dash(title=...)` — the <title> and `resolve_site_title`'s fallback."""
    assert app.title == EXPECTED_BRAND


def test_home_prose_opens_with_the_brand():
    first = (REPO_ROOT / "pages" / "home.md").read_text().splitlines()[0]
    assert first == f"# {EXPECTED_BRAND}"


def test_llms_index_h1_is_the_brand(client):
    """The single most-read line of this site, and the one nobody looks at."""
    response = client.get("/llms.txt")
    assert response.ok
    assert response.text.splitlines()[0] == f"# {EXPECTED_BRAND}"


def test_llms_index_tagline_is_the_description(client):
    body = client.get("/llms.txt").text
    assert f"> {SITE_DESCRIPTION}" in body


def test_the_viewer_brand_chip_is_not_a_framework_default(client):
    """The chip that read "Dash" on the pre-2.3.4 artifact.

    It is rendered from the same `resolve_site_title` call as the H1, so
    asserting the brand is present and the default is absent catches both a
    stale package and a regressed constant.
    """
    import html as html_module

    from conftest import BROWSER_ACCEPT

    page = client.get("/quick-start/llms.txt", accept=BROWSER_ACCEPT).text
    # The banner is templated markup, so the brand arrives escaped — the
    # apostrophe in "network's" becomes `&#x27;`. Comparing the raw string
    # here would fail for a reason that has nothing to do with identity.
    assert html_module.escape(EXPECTED_BRAND) in page, (
        "the viewer banner does not name this site"
    )


def test_the_package_name_is_in_the_description_not_the_brand():
    """Naming rules from the standard, both directions.

    The brand says what the site *is*; the package name and the byline belong
    in the description. A brand of "Pip Install Python" would make every
    satellite in the network share one name.
    """
    # THE RULE FLIPS BETWEEN TEMPLATE AND LIBRARY (network STANDARD §1).
    #
    # The boilerplate keeps its package name OUT of the brand, because nobody
    # installs a template — this test was inherited asserting exactly that.
    # Every *library* satellite does the opposite: the package name comes
    # FIRST, so a reader who meets the brand anywhere learns what to pip
    # install. Compare `dash-leaflet2 — Leaflet 2 maps for Dash`.
    #
    # So the assertion is inverted here, deliberately, and both halves are
    # still pinned: the brand leads with the package name, and the byline
    # stays out of it.
    assert SITE_BRAND.startswith("dash-model-viewer")
    assert "dash-model-viewer" in SITE_DESCRIPTION
    assert "Pip Install Python" not in SITE_BRAND
    assert "Pip Install Python" in SITE_DESCRIPTION
    assert "Pip Install Python" not in SITE_BRAND


# ---------------------------------------------------------------------------
# The meta description, and the copy of it that lives in the static template
# ---------------------------------------------------------------------------

# Google truncates meta descriptions around 155 characters. 160 is the ceiling
# rather than 155 so a one-word edit does not fail the suite, but the intent is
# the shorter number.
META_DESCRIPTION_LIMIT = 160


def test_the_meta_description_fits_in_a_search_result():
    """A description Google cuts in half is a description half-written.

    `register_page(description=)` publishes this verbatim as
    <meta name="description">, og:description and twitter:description. This
    site shipped 360 characters, so everything after "...with Augmented
    Reality (AR) support" — including the part that says why this package
    exists at all — never appeared in a result or a social preview.

    The long prose belongs on the home page, in the README and in /llms.txt,
    none of which are length-penalised. This is a tagline, not a summary.
    """
    assert len(SITE_DESCRIPTION) <= META_DESCRIPTION_LIMIT, (
        f"SITE_DESCRIPTION is {len(SITE_DESCRIPTION)} characters; search "
        f"results cut it at roughly {META_DESCRIPTION_LIMIT}."
    )


def test_the_static_template_repeats_the_same_description():
    """templates/index.html hard-codes a JSON-LD description, and it drifted.

    It cannot import lib.constants — it is a static template — so the string is
    duplicated by hand, and a hand-duplicated string is one that will disagree
    eventually. It already did: this file shipped carrying the BOILERPLATE's
    description, its softwareVersion and its GitHub repo, on a page whose
    <title> said dash-model-viewer. Nothing a human reads showed it; only the
    crawler document was wrong.

    So the duplicate is allowed, and checked.
    """
    html = (REPO_ROOT / "templates" / "index.html").read_text()
    # The template escapes the em dash as a JSON \u2014 escape.
    expected = SITE_DESCRIPTION.replace("—", "\\u2014")
    assert f'"description": "{expected}"' in html, (
        "templates/index.html's JSON-LD description does not match "
        "SITE_DESCRIPTION. Update the template to the same sentence — two "
        "descriptions means the crawler and the browser are told different "
        "things about the same site."
    )


def test_meta_keywords_describe_this_app_not_the_template():
    """Inherited keywords are a fork that never introduced itself.

    Google has ignored this tag since 2009, so nothing here moves a ranking —
    but other consumers read it, and a page whose keywords say "markdown docs,
    documentation, developer tools" is describing the boilerplate it was
    forked from rather than a 3D and AR component.
    """
    html = (REPO_ROOT / "templates" / "index.html").read_text()
    match = re.search(r'<meta name="keywords" content="([^"]*)"', html)
    assert match, "no keywords meta tag"
    terms = [t.strip().lower() for t in match.group(1).split(",")]

    assert "dash-model-viewer" in terms, "the keywords do not name the package"
    for subject in ("3d", "ar", "model-viewer"):
        assert any(subject in t for t in terms), (
            f"no keyword mentions {subject!r} — these are the terms this site "
            "should actually be found for"
        )
    # The template's own leftovers, which said nothing about 3D.
    for inherited in ("markdown docs", "documentation", "developer tools"):
        assert inherited not in terms, (
            f"{inherited!r} is an inherited boilerplate keyword"
        )


def test_no_surface_falls_back_to_a_generic_title():
    """The values `resolve_site_title` is designed to skip.

    If the brand were ever set to one of these, the package would silently
    fall through to the next candidate and this repo would have no idea which
    string it was publishing.
    """
    from dash_improve_my_llms.handlers import _GENERIC_SITE_TITLES

    assert SITE_BRAND.strip().lower() not in _GENERIC_SITE_TITLES


def test_readme_and_docs_agree_with_the_brand():
    """A README that names the site differently is the next drift."""
    readme = (REPO_ROOT / "README.md").read_text()
    assert EXPECTED_BRAND in readme, "README.md does not state the site brand"


def test_llms_package_floor_is_the_network_standard():
    """Identity resolution lives in the package; the floor is what delivers it."""
    import dash_improve_my_llms as pkg

    parts = tuple(int(p) for p in pkg.__version__.split(".")[:3] if p.isdigit())
    assert parts >= (2, 3, 4), (
        f"dash-improve-my-llms {pkg.__version__} predates resolve_site_title; "
        "the viewer chip and the /llms.txt H1 would fall back to app.title"
    )


# ---------------------------------------------------------------------------
# The per-page title — a share-card surface, not just a browser tab
#
# Dash passes each page's `title` straight into `og:title` and `twitter:title`
# (dash/_pages.py `_page_meta_tags`). PAGE_TITLE_PREFIX therefore sets the
# headline of every unfurl this site produces, and it read the FORK SOURCE's
# brand ("Dash Pip Components | ") in production until 1.2.2 — while every
# other surface correctly said this site's name. Nobody sees their own share
# cards, so only a test catches it.
# ---------------------------------------------------------------------------


def test_the_page_title_prefix_is_this_site():
    assert PAGE_TITLE_PREFIX == f"{SITE_SHORT_NAME} | "
    assert "Dash Pip Components" not in PAGE_TITLE_PREFIX, (
        "the fork source's brand is back in every share card"
    )


def test_the_short_name_cannot_drift_from_the_brand():
    """Two constants, one identity. Derived, so this should be automatic."""
    assert SITE_BRAND.startswith(SITE_SHORT_NAME)


def test_the_share_card_headline_names_this_site(client):
    """og:title and twitter:title, as a scraper reads them."""
    html = client.get("/").text
    for tag in ("og:title", "twitter:title"):
        found = re.findall(
            rf'<meta[^>]*property="{tag}"[^>]*content="([^"]*)"', html
        )
        assert found, f"no {tag} on the home page"
        for value in found:
            assert "Dash Pip Components" not in value, (
                f"{tag}={value!r} advertises the fork source"
            )
            assert SITE_SHORT_NAME in value, f"{tag}={value!r} does not name this site"


def test_no_surface_still_carries_the_fork_source_brand():
    """A sweep, because the prefix was not the only place it could hide."""
    offenders = []
    for path in ("lib/constants.py", "templates/index.html", "pages/home.md",
                 "assets/favicon/site.webmanifest"):
        text = (REPO_ROOT / path).read_text()
        # The constants file documents the old value in a comment explaining
        # the fix; that is the one legitimate mention.
        stripped = re.sub(r"#.*", "", text) if path.endswith(".py") else text
        stripped = re.sub(r"<!--.*?-->", "", stripped, flags=re.S)
        if "Dash Pip Components" in stripped:
            offenders.append(path)
    assert offenders == [], f"the fork source's brand survives in {offenders}"


def test_home_markdown_is_not_a_stale_copy_of_the_old_opening():
    """`# Welcome to:` was the old H1 — an identity that named nothing."""
    body = Path(REPO_ROOT / "pages" / "home.md").read_text()
    assert "# Welcome to:" not in body
