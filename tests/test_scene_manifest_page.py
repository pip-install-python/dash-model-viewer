"""The schema page must not invent numbers.

Every bound the page quotes is a constant in `lib/sculptor.py`. A documented
limit that disagrees with the enforced one is the defect class this whole
release spent its time removing — `src`/`alt` were "required" in three places
and checked in none.

The round-trip and refusal tests belong with the importer and exporter, which
do not exist yet. This file covers what can be true before them: that the page
and the code agree.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from lib import sculptor

REPO = pathlib.Path(__file__).resolve().parent.parent
PAGE = REPO / "docs" / "scene-manifest" / "scene-manifest.md"


@pytest.fixture(scope="module")
def prose():
    text = PAGE.read_text(encoding="utf-8")
    return " ".join(text.replace("*", "").replace("`", "").split())


def test_the_page_exists_and_is_not_empty(prose):
    """Guard the guard: every assertion below is vacuous against an empty file."""
    assert len(prose) > 3000, f"page is only {len(prose)} chars"


# --------------------------------------------------------------------------
# The bounds, each read from the code
# --------------------------------------------------------------------------


def test_the_part_limit_matches_the_code(prose):
    assert f"{sculptor.MAX_PARTS} parts" in prose


def test_the_extent_bound_matches_the_code(prose):
    assert f"{sculptor.MAX_EXTENT:g} m" in prose


def test_the_scene_radius_matches_the_code(prose):
    assert f"{sculptor.MAX_SCENE_RADIUS:g} m" in prose


def test_the_output_ceiling_matches_the_code(prose):
    assert f"{sculptor.MAX_GLB_BYTES // 1_000_000} MB" in prose


def test_every_shape_in_the_vocabulary_is_documented(prose):
    for shape in sculptor.SHAPES:
        assert shape in prose, f"{shape} is in SHAPES and not on the page"


def test_the_page_offers_EXACTLY_the_real_vocabulary():
    """The inverse of the test above, and the half a reader gets burned by.

    Asserted against the shape row of the part table, parsed as a row rather
    than sampled from a character window — a window after the first occurrence
    of "shape" passes or fails on where the word happens to appear, which is
    not a property worth testing.
    """
    row = next(
        line for line in PAGE.read_text(encoding="utf-8").splitlines()
        if line.startswith("| `shape`")
    )
    offered = set(re.findall(r"`([a-z]+)`", row)) - {"shape"}
    assert offered == set(sculptor.SHAPES), (
        f"the page offers {sorted(offered)}; the code accepts "
        f"{sorted(sculptor.SHAPES)}"
    )


def test_the_roughness_floor_matches_the_clamp():
    """Read from the source, because the floor is a literal in a call."""
    src = (REPO / "lib" / "sculptor.py").read_text(encoding="utf-8")
    m = re.search(r'_clamp\(part\.get\("roughness"\),\s*([0-9.]+)', src)
    assert m, "could not find the roughness clamp"
    floor = m.group(1)
    prose = " ".join(PAGE.read_text(encoding="utf-8").split())
    assert floor in prose, f"the page does not state the {floor} roughness floor"


# --------------------------------------------------------------------------
# Units and frame, stated once
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "claim",
    [
        "metres",
        "degrees, not radians",
        "right-handed",
        "+Y",
        "centre",
    ],
)
def test_the_frame_is_stated(prose, claim):
    assert claim.lower() in prose.lower(), f"the page does not state: {claim}"


# --------------------------------------------------------------------------
# The decisions the version number depends on
# --------------------------------------------------------------------------


def test_the_page_says_unknown_keys_are_REJECTED(prose):
    """The draft said "ignored", which breaks the guarantee the version makes:
    a version 2 manifest using part groups would be accepted by a version 1
    reader and render without them, silently."""
    assert "unknown keys are rejected" in prose.lower()
    assert "unknown keys are ignored" not in prose.lower()


def test_the_page_says_an_unknown_version_is_not_partially_read(prose):
    assert "not partially read" in prose.lower()


def test_provenance_is_documented_as_never_read(prose):
    """A manifest must be sufficient to re-render WITHOUT the prompt; the
    prompt, model and cost are provenance, not input."""
    assert "provenance" in prose.lower()
    assert "renderer never needs the prompt" in prose.lower()


def test_the_page_commits_to_version_1_not_changing_meaning(prose):
    assert "version 1 will not change meaning" in prose.lower()
    assert "version 2" in prose.lower(), "the additive plan is not stated"


# --------------------------------------------------------------------------
# Where the samples come from, and what is not stored
# --------------------------------------------------------------------------


def test_the_page_is_honest_about_where_the_samples_came_from(prose):
    """A DEVIATION from the seat's spec, stated rather than slipped in.

    The spec said the samples are "generated locally with keys". They are
    HAND-AUTHORED, for two reasons: a model will not produce exactly 28 parts
    on request, and the inclusive limit is the thing worth proving on the wire;
    and a hand-authored file costs nothing to regenerate when the schema gains
    a version 2.

    So the page must not claim a model wrote them, and their provenance must
    not name one.
    """
    assert "hand-authored, not model output" in prose.lower()
    assert "carries no provider keys" in prose.lower()
    assert "generated locally, with api keys" not in prose.lower()


def test_no_sample_claims_a_model_it_did_not_come_from():
    """The honesty above, as a property of the files rather than the prose."""
    import json

    samples = REPO / "docs" / "scene-manifest" / "samples"
    files = sorted(samples.glob("*.json"))
    assert files, "no samples to check"
    for path in files:
        provenance = json.loads(path.read_text(encoding="utf-8")).get("provenance")
        if not provenance:
            continue
        assert provenance.get("model") == "hand-authored", (
            f"{path.name} names {provenance.get('model')!r} as its author"
        )
        assert provenance.get("usd", 0) == 0, f"{path.name} claims a cost"


def test_the_page_states_the_no_store_rule(prose):
    for claim in ("never written to disk", "no manifest store"):
        assert claim in prose.lower(), f"the page does not state: {claim}"
