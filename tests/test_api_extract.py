"""/api has rows in BOTH lanes, from a package that ships no metadata.json.

Sync item 18's contract (7-amended) names four mechanisms that produce an
empty `/api` answering 200, and this file pins the two that can happen here:

  3. upstream `load_package` returns `[]` SILENTLY when `metadata.json` is
     absent. It is absent here permanently — `dash_model_viewer` is
     hook-based since 1.0.0, there is no generator, and
     `tests/test_no_regeneration.py` fails if one ever reappears. So the
     REQUIRED committed-extract-or-docstring road is the only road, and the
     item's pin — resolve metadata into an empty dir, assert components
     still come back — is the one below.
  4. a directive that renders Dash components into the React tree only.
     Not applicable to `/api` (its tables are built in `pages/api.py`, not
     by a directive) but the lane-parity pin here is written the way the
     item asks anyway: assert ROWS and row CONTENT, never headings.

`tests/test_nav_contract.py` is byte-identical to the template's and carries
neither pin — the template documents no component package, so it has nothing
to point them at. Reported to the seat as a gap; this file is the fork half.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PACKAGE = "dash_model_viewer"
EXTRACT = REPO / PACKAGE / "api_metadata.json"


def _docstring_components():
    """Source 3 alone — what the classes themselves say, right now."""
    import importlib

    from lib import api_reference

    return api_reference._from_docstrings(importlib.import_module(PACKAGE))


def test_components_survive_a_package_with_no_metadata_json():
    """The item's required pin, and it is not hypothetical here.

    Resolve BOTH machine-readable files away and assert the tables still
    come back. A fork that only ever tests the happy path ships a page that
    is 200, canonical, single-h1 — and empty.
    """
    import importlib

    from lib import api_reference

    mod = importlib.import_module(PACKAGE)
    pkg_dir = Path(mod.__file__).resolve().parent
    assert not (pkg_dir / "metadata.json").exists(), (
        "a metadata.json appeared in the package — tests/test_no_regeneration.py "
        "should have caught it first; this repo's components are hand-authored"
    )

    components = api_reference._from_docstrings(mod)
    assert [c["name"] for c in components] == ["ModelViewer", "Slot"]
    props = {p["name"]: p for p in components[0]["props"]}
    assert props["src"]["required"] and props["alt"]["required"]
    assert props["ar"]["default"] == "True"
    assert props["alt"]["description"].startswith("Accessible description")


def test_the_committed_extract_still_matches_the_docstrings():
    """The extract is a SECOND source of truth, so it can go stale.

    `load_package` prefers it over the docstrings, which is what makes
    `/api`'s lastmod stable across Docker rebuilds — and also what would let
    a prop change silently not reach the page. Regenerate with
    `python scripts/build_api_metadata.py` and commit it in the same change
    as the prop.
    """
    assert EXTRACT.is_file(), (
        f"{EXTRACT.name} is missing — /api falls back to the docstrings and "
        "its sitemap lastmod disappears; run scripts/build_api_metadata.py"
    )
    data = json.loads(EXTRACT.read_text())
    assert data["components"] == _docstring_components(), (
        "the committed extract disagrees with the classes it was built from — "
        "run `python scripts/build_api_metadata.py` and commit the result"
    )
    assert data["generated"], "the extract carries no `generated` date"


def test_the_extract_reaches_the_wheel():
    """Present in a checkout and MISSING on the host is the exact split sync
    item 18 exists to close: the site installs this package with
    `pip install --no-deps .`, so an extract outside the wheel would give a
    developer a dated /api and production an undated one."""
    manifest = (REPO / "MANIFEST.in").read_text()
    pyproject = (REPO / "pyproject.toml").read_text()
    assert f"include {PACKAGE}/api_metadata.json" in manifest, "MANIFEST.in"
    assert '"api_metadata.json"' in pyproject, "pyproject package-data"


def test_api_lastmod_comes_from_the_extract():
    from lib import api_reference

    stamp = api_reference.slim_generated_on(PACKAGE)
    assert stamp == json.loads(EXTRACT.read_text())["generated"]
    assert stamp, "/api would carry no lastmod"


@pytest.mark.parametrize("component,prop", [("ModelViewer", "src"), ("Slot", "slot")])
def test_both_lanes_carry_THE_ROWS_not_just_the_headings(client, app_module, component, prop):
    """Lane parity, asserted on row CONTENT (the item's test lesson).

    A heading assertion passes on an empty table, which is how the fleet's
    /api shipped silence while every structural check stayed green. These
    name a component and one of its props and require both in both lanes.

    Which artifacts are measured, named explicitly because "the browser
    lane" is three things: (1) the crawler document, served to a crawler UA;
    (2) the `/api/llms.txt` machine document. The JS-rendered DOM is NOT
    measured here — no test client renders React — which is why
    tests/test_layout_nesting.py exists alongside this file.
    """
    crawler = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"

    machine = client.get("/api/llms.txt", user_agent=crawler)
    assert machine.status == 200
    assert f"### {component}" in machine.text, machine.text[:200]
    assert f"| `{prop}`" in machine.text, f"{prop} row missing from the machine lane"

    crawler_html = client.get("/api", user_agent=crawler)
    assert crawler_html.status == 200
    assert component in crawler_html.text
    assert prop in crawler_html.text, f"{prop} row missing from the crawler document"
