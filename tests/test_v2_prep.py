"""The v2 preparation: inert constants, the v2 prompt, the prompt-set proposal.

Nothing here is wired into a page or run against a model. These tests exist so
the prep cannot rot between being written and G1 being built — and so the v2
prompt is held to the same standard as v1's the day it lands rather than the
day someone notices.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from lib import manifest, sculptor

REPO = pathlib.Path(__file__).resolve().parent.parent
PROMPTS = REPO / "docs" / "benchmark" / "prompts.json"


# --------------------------------------------------------------------------
# The caps exist before the code that enforces them
# --------------------------------------------------------------------------


def test_the_v2_caps_are_named_constants():
    """So the page rows and the validator cannot be written against different
    numbers — which is note 194b applied to numbers rather than to prose."""
    assert sculptor.MAX_DEPTH == 4
    assert sculptor.MAX_DEFS == 8
    assert sculptor.MAX_PARTS == 28


def test_the_caps_are_now_ENFORCED_not_merely_declared():
    """This test used to assert the opposite.

    While the caps were prep, it asserted nothing imported them — so that
    building against them early would be noticed. G1 has landed, so the useful
    question inverted: are they actually enforced, or still just documented?
    A declared limit nobody checks is the defect class 1.0.0 spent its review
    removing.
    """
    import subprocess

    out = subprocess.run(
        ["git", "grep", "-l", "MAX_DEPTH\\|MAX_DEFS", "--", "*.py"],
        capture_output=True, text=True, cwd=REPO,
    ).stdout.split()
    assert "lib/manifest.py" in out, (
        "the validator does not mention the caps — they are documentation, "
        "not limits"
    )

    deep = {"version": 2, "defs": {}, "parts": []}
    node = deep["parts"]
    for _ in range(sculptor.MAX_DEPTH + 1):
        child = []
        node.append({"group": "g", "position": {"x": 0, "y": 0, "z": 0},
                     "children": child})
        node = child
    node.append({"name": "p", "shape": "box",
                 "size": {"x": 0.2, "y": 0.2, "z": 0.2},
                 "position": {"x": 0, "y": 0, "z": 0},
                 "rotation": {"x": 0, "y": 0, "z": 0},
                 "color": "#888888", "metallic": 0.0,
                 "roughness": 0.8, "emissive_strength": 0.0})
    with pytest.raises(manifest.ManifestError, match="nest more than"):
        manifest.validate(deep)

    too_many = {
        "version": 2,
        "defs": {f"d{i}": {"children": [{"name": "p", "shape": "box",
                                         "size": {"x": 0.2, "y": 0.2, "z": 0.2},
                                         "position": {"x": 0, "y": 0, "z": 0},
                                         "rotation": {"x": 0, "y": 0, "z": 0},
                                         "color": "#888888", "metallic": 0.0,
                                         "roughness": 0.8,
                                         "emissive_strength": 0.0}]}
                 for i in range(sculptor.MAX_DEFS + 1)},
        "parts": [{"ref": "d0", "position": {"x": 0, "y": 0, "z": 0}}],
    }
    with pytest.raises(manifest.ManifestError, match="the limit is"):
        manifest.validate(too_many)


# --------------------------------------------------------------------------
# The v2 prompt
# --------------------------------------------------------------------------


def test_the_v2_prompt_exists_and_is_inert():
    assert sculptor.SYSTEM_V2
    assert sculptor.SYSTEM_V2 is not sculptor.SYSTEM


def test_the_v2_prompt_renders_the_shared_size_table():
    """The radius/diameter error must not be able to reappear in the new prompt
    either — it renders the same object v1 does."""
    for shape, meaning in sculptor.size_semantics_rows():
        assert meaning in sculptor.SYSTEM_V2, shape
    block = sculptor.SYSTEM_V2.split("PRIMITIVES", 1)[1].split("\n\n", 1)[0]
    assert "radius" not in block.lower()


def test_the_v2_prompt_says_size_is_never_a_radius():
    assert "NEVER A RADIUS" in sculptor.SYSTEM_V2


@pytest.mark.parametrize("concept", ["defs", "ref", "group", "children"])
def test_the_v2_prompt_teaches_the_new_vocabulary(concept):
    assert concept in sculptor.SYSTEM_V2, f"v2 does not mention {concept}"


def test_the_v2_prompt_states_every_cap_from_the_constants():
    for cap in (sculptor.MAX_PARTS, sculptor.MAX_DEFS, sculptor.MAX_DEPTH):
        assert str(cap) in sculptor.SYSTEM_V2, cap


def test_the_v2_prompt_says_the_budget_counts_LEAVES():
    """The number is unchanged and its meaning is not; a model that thinks 28
    counts references will overshoot by the size of its defs."""
    assert "LEAF parts after expansion" in sculptor.SYSTEM_V2


def test_the_worked_examples_arithmetic_is_right():
    """The cart: a 2-leaf wheel placed 4 times, plus a bed.

    The first draft of this line said "nine leaf parts, not twelve written out
    by hand". Nine was right; twelve was wrong — expansion does not change the
    leaf count, so by hand it is nine too. The saving is in entries WRITTEN
    (seven), not in leaves. A worked example with bad arithmetic teaches the
    model to mis-budget.
    """
    text = sculptor.SYSTEM_V2
    assert "nine LEAF parts after expansion" in text
    assert "eight wheel parts plus the bed" in text
    assert "seven entries written" in text
    assert "not twelve" not in text


def test_the_worked_example_places_one_def_four_times():
    example = sculptor.SYSTEM_V2.split("A WORKED EXAMPLE", 1)[1]
    assert example.count('"ref": "wheel"') == 4
    assert example.count('"defs"') == 1


# --------------------------------------------------------------------------
# The prompt-set proposal
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def proposal():
    return json.loads(PROMPTS.read_text(encoding="utf-8"))


def test_the_prompt_set_is_marked_as_a_proposal(proposal):
    """Q2 is the owner's. A file that looked decided would take their choice
    away by being easier to leave alone than to change."""
    assert "PROPOSAL" in proposal["_proposal"]
    assert "not a decision" in proposal["_proposal"]


def test_there_are_eight_prompts(proposal):
    assert len(proposal["prompts"]) == 8


def test_every_prompt_has_a_documented_class(proposal):
    classes = set(proposal["_classes"])
    for p in proposal["prompts"]:
        assert p["class"] in classes, p["id"]
        assert p["text"] and p["why"]


def test_the_set_can_separate_the_bug_fix_from_the_vocabulary(proposal):
    """THE REASON THE CLASSES EXIST. Note 197 halved every curved part, so a
    set of only curve-dominant subjects would credit v2 with that fix. At least
    one box-dominant subject is required as the control."""
    classes = [p["class"] for p in proposal["prompts"]]
    assert "box-dominant" in classes, (
        "without a box-dominant control the before/after cannot separate "
        "'v2 is better' from 'the curves are no longer half size'"
    )
    assert classes.count("repetition") >= 2, "defs/ref need more than one subject"
    assert "silhouette" in classes, "G3 needs a subject it alone can serve"
    assert "unsuited" in classes, "the table needs a floor"


def test_the_set_records_that_the_v1_leg_is_the_CORRECTED_prompt(proposal):
    assert "CORRECTED v1" in proposal["_note"]


def test_ids_are_unique(proposal):
    ids = [p["id"] for p in proposal["prompts"]]
    assert len(set(ids)) == len(ids)
