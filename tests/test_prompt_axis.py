"""/benchmark's prompt-version axis — measuring v2 before believing it.

THE POINT. SYSTEM_V2 is better by ARGUMENT: it teaches defs/ref/group and tells
a model that parts may interpenetrate where they join. The entire claim is "it
produces better sculptures", and only model runs can show that. So it ships
SELECTABLE HERE and default NOWHERE, and this file is what holds that line —
if v2 ever becomes the default on a page that generates sculptures, these tests
go red.

Nothing here calls a model. The axis is tested as wiring and policy; whether v2
actually helps is the owner's sweep to run, and its gate is a spend decision,
not a test.
"""

from __future__ import annotations

import importlib
import inspect
import pathlib

import pytest

from lib import sculptor

REPO = pathlib.Path(__file__).resolve().parent.parent
PAGE = importlib.import_module("docs.benchmark.benchmark")


def _part(name, x):
    return {"name": name, "shape": "box",
            "size": {"x": 1, "y": 1, "z": 1},
            "position": {"x": x, "y": 0, "z": 0},
            "rotation": {"x": 0, "y": 0, "z": 0},
            "color": "#888888", "metallic": 0.0,
            "roughness": 0.8, "emissive_strength": 0.0}


# --------------------------------------------------------------------------
# The line this file exists to hold
# --------------------------------------------------------------------------


def test_v1_is_the_default_in_the_library():
    assert sculptor.DEFAULT_PROMPT_VERSION == "v1"
    assert sculptor.system_for(sculptor.DEFAULT_PROMPT_VERSION) is sculptor.SYSTEM
    assert inspect.signature(sculptor.sculpt).parameters[
        "prompt_version"].default == "v1"


@pytest.mark.parametrize("path", [
    "docs/generative-3d/sculptor.py",
    "docs/sculpt-from-image/sculpt_from_image.py",
])
def test_no_generating_page_selects_v2(path):
    """THE GATE. A page that generates sculptures must not pass a prompt
    version at all — it takes the default, and the default is v1 until a sweep
    earns the change."""
    source = (REPO / path).read_text(encoding="utf-8")
    assert "prompt_version" not in source, (
        f"{path} chooses a prompt version; v2 is measured on /benchmark and "
        f"promoted in its own commit, citing a table"
    )
    assert "SYSTEM_V2" not in source


def test_only_the_benchmark_passes_a_prompt_version():
    """Read across the whole tree rather than the two pages above, so a third
    page added later cannot quietly opt in."""
    import subprocess

    out = subprocess.run(
        ["git", "grep", "-l", "prompt_version", "--", "docs/", "lib/"],
        capture_output=True, text=True, cwd=REPO,
    ).stdout.split()
    assert out, "the sweep found nothing — it is not reading the tree"
    assert set(out) <= {"docs/benchmark/benchmark.py", "lib/sculptor.py"}, (
        f"prompt_version is chosen outside /benchmark: {out}"
    )


def test_an_unknown_version_falls_back_rather_than_raising():
    """Reached from a sweep; a stale control value should run the shipped
    prompt, not take the page down."""
    for bad in ("", None, "v3", "SYSTEM_V2"):
        assert sculptor.system_for(bad) is sculptor.SYSTEM


# --------------------------------------------------------------------------
# The axis itself
# --------------------------------------------------------------------------


def test_the_prompt_axis_varies_only_the_prompt():
    """The reason the axis is worth having: everything else is held, so a
    difference in the result is attributable to the instructions."""
    cells = PAGE._variants("prompt", ["low"], ["4000"], ["m1", "m2"],
                           "claude-opus-5", "low", 4000, ["v1", "v2"], "v1")
    assert [c[3] for c in cells] == ["v1", "v2"]
    assert len({(c[0], c[1], c[2]) for c in cells}) == 1, "something else moved"


@pytest.mark.parametrize("axis,expect", [
    ("effort", ["v2", "v2"]),
    ("budget", ["v2", "v2"]),
    ("model", ["v2", "v2"]),
])
def test_every_other_axis_holds_the_fixed_prompt_version(axis, expect):
    cells = PAGE._variants(axis, ["low", "high"], ["2000", "8000"], ["m1", "m2"],
                           "claude-opus-5", "low", 4000, ["v1"], "v2")
    assert [c[3] for c in cells] == expect


def test_the_axis_is_capped_like_the_others():
    cells = PAGE._variants("prompt", [], [], [], "m", "low", 4000,
                           ["v1", "v2"] * 5, "v1")
    assert len(cells) <= PAGE.MAX_VARIANTS


def test_a_missing_fixed_version_falls_back_to_the_default():
    cells = PAGE._variants("model", [], [], ["m1"], "m", "low", 4000, [], None)
    assert cells[0][3] == sculptor.DEFAULT_PROMPT_VERSION


def test_the_result_label_names_the_prompt_version():
    """Without it, two cells in a prompt sweep are indistinguishable."""
    result = sculptor.SculptResult(ok=True, model="claude-opus-5", effort="low",
                                   max_tokens=4000, prompt_version="v2")
    assert "prompt v2" in PAGE.result_label(result)


def test_a_failed_variant_still_records_which_prompt_it_used():
    source = inspect.getsource(PAGE._run)
    assert "prompt_version=version" in source, (
        "a variant that errors must still say which prompt produced the error"
    )


# --------------------------------------------------------------------------
# The column the axis exists to move
# --------------------------------------------------------------------------


def test_the_panel_reports_the_interpenetration_rate():
    result = sculptor.SculptResult(
        ok=True, manifest={"parts": [_part("a", 0.0), _part("b", 0.9)]})
    assert PAGE.blend(result) == "1/1 joints blend (100%)"


def test_touching_is_not_blending():
    """The boundary that makes the number mean anything: two parts that merely
    meet read as objects stacked, which is the rigidity being measured."""
    result = sculptor.SculptResult(
        ok=True, manifest={"parts": [_part("a", 0.0), _part("b", 1.0)]})
    assert PAGE.blend(result) == "0/1 joints blend (0%)"


def test_scattered_parts_report_no_joints_rather_than_zero_percent():
    result = sculptor.SculptResult(
        ok=True, manifest={"parts": [_part("a", 0.0), _part("b", 3.0)]})
    assert "no joints" in PAGE.blend(result)


@pytest.mark.parametrize("result", [
    sculptor.SculptResult(ok=False, reason="boom"),
    sculptor.SculptResult(ok=True, manifest={}),
    sculptor.SculptResult(ok=True, manifest={"parts": [{"shape": "nonsense"}]}),
])
def test_the_column_never_raises_into_the_page(result):
    """It is decoration on a result that already cost money; it must not be
    able to lose the sculpture it describes."""
    assert isinstance(PAGE.blend(result), str)


# --------------------------------------------------------------------------
# The page says what it does
# --------------------------------------------------------------------------


def test_the_page_explains_why_v2_is_not_the_default():
    prose = (REPO / "docs/benchmark/benchmark.md").read_text(encoding="utf-8")
    assert "four axes" in prose, "the axis count is stale"
    assert "not the default" in prose
    assert "here and nowhere else" in prose
    assert "blend" in prose.lower()


def test_the_v2_prompt_still_carries_what_the_page_claims_for_it():
    """The page tells a reader what v2 adds; if the prompt stops saying it, the
    page is lying."""
    assert "MAY AND SHOULD INTERPENETRATE" in sculptor.SYSTEM_V2
    for concept in ("defs", "ref", "group"):
        assert concept in sculptor.SYSTEM_V2
