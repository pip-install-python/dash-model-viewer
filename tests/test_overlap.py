"""The interpenetration metric — "blend better" turned into a number.

The owner said the output is "a lot of rigid shapes … able to blend better
together". That is a judgement, and G1's before/after table needs a figure. This
module measures, from geometry alone, what fraction of the joints in a sculpture
actually interpenetrate rather than merely touching.

The tests matter because the metric's boundary case IS the measurement: two
surfaces that meet exactly are the rigidity being complained about, so tangency
must count as a gap. A metric that counted it as an overlap would score the
rigid case 100% and measure nothing.
"""

from __future__ import annotations

import pathlib

from lib import manifest, overlap

REPO = pathlib.Path(__file__).resolve().parent.parent
SAMPLES = REPO / "docs" / "scene-manifest" / "samples"


def _part(name, shape="box", size=(1, 1, 1), pos=(0, 0, 0), rot=(0, 0, 0)):
    return {
        "name": name, "shape": shape,
        "size": {"x": size[0], "y": size[1], "z": size[2]},
        "position": {"x": pos[0], "y": pos[1], "z": pos[2]},
        "rotation": {"x": rot[0], "y": rot[1], "z": rot[2]},
        "color": "#888888", "metallic": 0.0,
        "roughness": 0.8, "emissive_strength": 0.0,
    }


def _scene(*parts):
    return {"version": 1, "name": "t", "parts": list(parts)}


# --------------------------------------------------------------------------
# Extents come from the geometry, not from a second copy of the size rules
# --------------------------------------------------------------------------


def test_the_box_extent_is_the_size():
    (lo, hi) = overlap.aabb(_part("b", "box", (2, 1, 0.5)))
    assert abs((hi[0] - lo[0]) - 2.0) < 1e-9
    assert abs((hi[1] - lo[1]) - 1.0) < 1e-9
    assert abs((hi[2] - lo[2]) - 0.5) < 1e-9


def test_the_sphere_extent_is_the_DIAMETER_not_the_radius():
    """Note 197's error, which this module would have repeated if it computed
    extents from `size` with its own idea of what size means."""
    (lo, hi) = overlap.aabb(_part("s", "sphere", (1, 1, 1)))
    assert abs((hi[0] - lo[0]) - 1.0) < 1e-9


def test_the_torus_extent_is_x_plus_z():
    (lo, hi) = overlap.aabb(_part("t", "torus", (3.0, 1, 0.2)))
    assert abs((hi[0] - lo[0]) - 3.2) < 1e-6


def test_rotation_changes_the_box():
    """A tilted part's box is the box of the tilted geometry. Ignoring rotation
    would make adjacency wrong for exactly the leaning parts the prompt asks
    for."""
    flat = overlap.aabb(_part("a", "box", (2, 0.1, 0.1)))
    tilted = overlap.aabb(_part("a", "box", (2, 0.1, 0.1), rot=(0, 0, 45)))
    assert (tilted[1][1] - tilted[0][1]) > (flat[1][1] - flat[0][1]) + 0.5


def test_an_unknown_shape_has_no_box():
    assert overlap.aabb(_part("x", "dodecahedron")) is None


# --------------------------------------------------------------------------
# The boundary that IS the measurement
# --------------------------------------------------------------------------


def test_exact_tangency_counts_as_a_GAP_not_an_overlap():
    """THE DEFINING CASE. Two 1 m cubes centred 1 m apart touch exactly. That
    is the "objects stacked in a pile" look the owner described, so it must not
    score as interpenetration — a metric that called it an overlap would rate
    the rigid case 100%."""
    r = overlap.report(_scene(
        _part("a", pos=(0, 0, 0)),
        _part("b", pos=(1.0, 0, 0)),
    ))
    assert r["overlapping"] == 0
    assert r["gapped"] == 1
    assert r["rate"] == 0.0


def test_a_millimetre_of_overlap_counts():
    r = overlap.report(_scene(
        _part("a", pos=(0, 0, 0)),
        _part("b", pos=(0.999, 0, 0)),
    ))
    assert r["overlapping"] == 1 and r["rate"] == 1.0


def test_a_small_gap_is_a_joint_and_a_large_one_is_not():
    near = overlap.report(_scene(_part("a"), _part("b", pos=(1.015, 0, 0))))
    far = overlap.report(_scene(_part("a"), _part("b", pos=(1.5, 0, 0))))
    assert near["joints"] == 1 and near["gapped"] == 1
    assert far["joints"] == 0, "distant parts are not a joint either way"


def test_no_joints_reports_None_rather_than_zero():
    """A sculpture of scattered parts has no interpenetration rate. Reporting
    0% would read as a failure to blend rather than as nothing to blend."""
    r = overlap.report(_scene(_part("a"), _part("b", pos=(3, 0, 0))))
    assert r["rate"] is None
    assert "no joints" in overlap.summary(_scene(_part("a"), _part("b", pos=(3, 0, 0))))


def test_the_tolerance_is_configurable_and_changes_the_answer():
    scene = _scene(_part("a"), _part("b", pos=(1.05, 0, 0)))
    assert overlap.report(scene, tolerance=0.02)["joints"] == 0
    assert overlap.report(scene, tolerance=0.10)["joints"] == 1


# --------------------------------------------------------------------------
# The samples, as the baseline G1 will be measured against
# --------------------------------------------------------------------------


def test_the_lighthouse_sample_has_the_gap_that_started_this():
    """tower top 2.000, lamp bottom 2.010 — the 10 mm gap that made the
    owner's "rigid shapes" concrete."""
    m = manifest.loads((SAMPLES / "lighthouse.json").read_text(encoding="utf-8"))
    r = overlap.report(m)
    assert r["joints"] == 1 and r["overlapping"] == 0
    (a, b, sep) = r["gap_pairs"][0]
    assert {a, b} == {"tower", "lamp"}
    assert abs(sep - 0.010) < 1e-6


def test_my_own_colonnade_sample_is_rigid_by_this_measure():
    """Recorded rather than quietly fixed. I hand-authored colonnade.json and
    sat all 24 columns exactly ON the floor — 25 tangent joints, a 17% rate.
    It is a faithful example of the thing being complained about, which makes
    it a better fixture than a corrected one would be."""
    m = manifest.loads((SAMPLES / "colonnade.json").read_text(encoding="utf-8"))
    r = overlap.report(m)
    assert r["gapped"] >= 20
    assert r["rate"] < 0.5


def test_the_brazier_sample_interpenetrates_fully():
    m = manifest.loads((SAMPLES / "brazier.json").read_text(encoding="utf-8"))
    assert overlap.report(m)["rate"] == 1.0


# --------------------------------------------------------------------------
# The guidance that should move the number
# --------------------------------------------------------------------------


def test_the_v2_prompt_asks_for_interpenetration_both_ways():
    """Positively, and against the prior — the shape the width sentence uses,
    because the error comes from a model's assumption rather than from missing
    information."""
    from lib import sculptor

    assert "MAY AND SHOULD INTERPENETRATE" in sculptor.SYSTEM_V2
    assert "not balanced on it" in sculptor.SYSTEM_V2
    assert "read as separate objects stacked" in sculptor.SYSTEM_V2


def test_the_v1_prompt_still_says_nothing_about_joints():
    """The baseline has to stay the baseline; if v1 gained this line the
    before/after would measure nothing."""
    from lib import sculptor

    for word in ("interpenetrate", "overlap", "INTO the"):
        assert word not in sculptor.SYSTEM, f"v1 now mentions {word!r}"
