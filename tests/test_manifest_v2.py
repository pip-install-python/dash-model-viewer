"""Manifest v2 — defs, groups and refs, and the instancing they buy.

THE ROW THIS CLOSES, from the owner's table: "hierarchy / instancing — none;
parts is still flat, groups is rejected".

WHAT IS BEING CLAIMED, and therefore what is tested:

1. A nested manifest puts every part exactly where the same sculpture written
   flat does. Not byte-identically — a flat cart gets one mesh per part by
   design, so the two files differ on purpose — but NODE FOR NODE.
2. Every placement of a def shares ONE mesh and ONE material, so the file gets
   smaller in proportion to how much the sculpture repeats itself.
3. The two shipped readers that reason about where parts ARE — the
   interpenetration metric and the texture projection — cannot tell a nested
   manifest from a flat one.
4. A v1 manifest renders byte-for-byte what it always rendered.

Nothing here calls a model.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import struct

import pytest

from lib import glb, manifest, overlap, sculptor, texture

REPO = pathlib.Path(__file__).resolve().parent.parent
SAMPLES = REPO / "docs" / "scene-manifest" / "samples"

#: The v1 output contract. These samples predate v2 and must survive it — the
#: whole point of a version number is that old files are unaffected.
#:
#: NOT A BYTE HASH, AND THE FIRST VERSION OF THIS WAS. A SHA-256 of the `.glb`
#: passed here and failed on every CI leg, because it encodes the machine's
#: libm: the geometry builders call `cos`/`sin`, and MEASURED ON THESE SAMPLES
#: 22% of the float64 values that reach the file sit within one ULP of a
#: float32 rounding boundary. Perturbing `math.cos`/`math.sin` by a single ULP
#: changes all three digests — so the digest was a fact about macOS, not about
#: the renderer. The contract is recorded structurally instead, and compared
#: with a tolerance far below anything a real change could hide in.
V1_FIXTURE = REPO / "tests" / "fixtures" / "v1_render.json"

#: Tolerance for the structural comparison. 1e-6 m is a thousandth of a
#: millimetre — orders of magnitude tighter than any change worth catching,
#: and orders of magnitude looser than a last-bit difference in `cos`.
TOLERANCE = 1e-6


def _load(name):
    return manifest.loads((SAMPLES / name).read_text(encoding="utf-8"))


def _gltf(data):
    length = struct.unpack("<I", data[12:16])[0]
    return json.loads(data[20:20 + length])


def _leaf(**kw):
    part = {
        "name": "p", "shape": "box",
        "size": {"x": 0.2, "y": 0.2, "z": 0.2},
        "position": {"x": 0, "y": 0, "z": 0},
        "rotation": {"x": 0, "y": 0, "z": 0},
        "color": "#888888", "metallic": 0.0,
        "roughness": 0.8, "emissive_strength": 0.0,
    }
    part.update(kw)
    return part


# --------------------------------------------------------------------------
# 1. The nested cart and the flat cart are the same sculpture
# --------------------------------------------------------------------------


def test_the_two_carts_place_every_node_identically():
    """THE ACCEPTANCE. Byte-identity is the wrong test and would fail for a
    reason that is not a defect; node-for-node placement is the real claim."""
    ref = _gltf(manifest.render(_load("cart.json"))[0])
    flat = _gltf(manifest.render(_load("cart-flat.json"))[0])

    assert len(ref["nodes"]) == len(flat["nodes"]) == 8
    for index, (a, b) in enumerate(zip(ref["nodes"], flat["nodes"])):
        assert a.get("translation") == b.get("translation"), f"node {index} moved"
        assert a.get("rotation") == b.get("rotation"), f"node {index} turned"


def test_only_the_nested_cart_shares_geometry():
    ref = _gltf(manifest.render(_load("cart.json"))[0])
    flat = _gltf(manifest.render(_load("cart-flat.json"))[0])

    assert len(flat["meshes"]) == 8, "written flat, every part is its own mesh"
    assert len(ref["meshes"]) == 4, "bed, wheel, axle, handle — the wheel once"
    # four wheel nodes, one wheel mesh
    wheel_nodes = [n for n in ref["nodes"] if n["name"] == "wheel"]
    assert len(wheel_nodes) == 4
    assert len({n["mesh"] for n in wheel_nodes}) == 1


def test_sharing_makes_the_file_smaller_and_the_saving_is_worth_having():
    ref = manifest.render(_load("cart.json"))[0]
    flat = manifest.render(_load("cart-flat.json"))[0]
    assert len(ref) < len(flat)
    saving = 1 - len(ref) / len(flat)
    assert saving > 0.5, f"only {saving:.0%} smaller — sharing is not working"


def test_a_def_gets_one_material_as_well_as_one_mesh():
    """Sharing is keyed by DEF, not by comparing appearances: a ref carries
    only a name, a position and a rotation, so it cannot restyle or resize what
    it places. That makes one-material-per-def true by construction."""
    ref = _gltf(manifest.render(_load("cart.json"))[0])
    assert len(ref["materials"]) == 4
    wheel = [n for n in ref["nodes"] if n["name"] == "wheel"]
    materials = {ref["meshes"][n["mesh"]]["primitives"][0]["material"] for n in wheel}
    assert len(materials) == 1


def test_sharing_is_OPT_IN_through_ref():
    """Two identical parts written out by hand stay two meshes. A hand-written
    manifest renders exactly as it reads, and dedup by appearance would make
    the output depend on a comparison rather than on what was written."""
    scene = {"version": 1, "parts": [_leaf(name="a"), _leaf(name="b")]}
    assert len(_gltf(manifest.render(scene)[0])["meshes"]) == 2


# --------------------------------------------------------------------------
# 2. THE TEST THAT PROVES THE RISK WAS HONOURED
# --------------------------------------------------------------------------


def test_both_shipped_readers_cannot_tell_the_two_carts_apart():
    """G1's flat-nodes decision was taken because `lib/overlap.py` and
    `lib/texture.py` assume a mesh's transform IS its world transform. This is
    the assertion that the decision held: both read the same world from the
    nested manifest as from the flat one."""
    ref, flat = _load("cart.json"), _load("cart-flat.json")

    a, b = overlap.report(ref), overlap.report(flat)
    assert a["parts"] == b["parts"] == 8, "both must measure all eight leaves"
    assert a["joints"] == b["joints"]
    assert a["overlapping"] == b["overlapping"]
    assert a["rate"] == b["rate"]

    def bounds(m):
        placements = manifest.expand(m)
        meshes = [overlap._mesh_for(p["style"], p) for p in placements]
        return texture.bounds([mesh for mesh in meshes if mesh])

    assert bounds(ref) == bounds(flat), "the photo would drape differently"


def test_the_metric_reads_leaves_not_entries():
    """A `ref` is an entry with no shape. A reader that did not expand would
    skip it and quietly compute a rate over the two inline parts."""
    assert overlap.report(_load("cart.json"))["parts"] == 8
    assert len(_load("cart.json")["parts"]) == 4, "four entries, eight leaves"


# --------------------------------------------------------------------------
# 3. Rotations compose; they do not add
# --------------------------------------------------------------------------


def test_rotations_compose_as_quaternions_not_as_added_angles():
    """THE CASE WHERE ADDING IS WRONG: a group tilted about X holding a part
    turned about Y.

    The axes matter, and the first pair I picked (parent Y, child X) was a case
    where the two agree in this Euler convention — the guard at the bottom
    caught it. Kept as a parametrised pair so the discrimination is checked
    rather than assumed.
    """
    scene = {
        "version": 2,
        "parts": [{
            "group": "turned", "position": {"x": 0, "y": 0, "z": 0},
            "rotation": {"x": 90, "y": 0, "z": 0},
            "children": [_leaf(rotation={"x": 0, "y": 90, "z": 0})],
        }],
    }
    got = manifest.expand(scene)[0]["quat"]
    correct = glb.quat_multiply(glb._euler_to_quat(90, 0, 0),
                                glb._euler_to_quat(0, 90, 0))
    naive = glb._euler_to_quat(90, 90, 0)

    assert got == pytest.approx(correct)
    assert got != pytest.approx(naive), (
        "composed and added agree here, so this case proves nothing — pick "
        "another pair of axes"
    )


def test_a_def_keeps_its_own_orientation_and_the_ref_adds_to_it():
    """A wheel is defined lying on its side and placed upright; both rotations
    apply."""
    scene = {
        "version": 2,
        "defs": {"w": {k: v for k, v in _leaf(rotation={"x": 90, "y": 0, "z": 0}).items()
                       if k != "position"}},
        "parts": [{"ref": "w", "position": {"x": 1, "y": 0, "z": 0},
                   "rotation": {"x": 0, "y": 45, "z": 0}}],
    }
    got = manifest.expand(scene)[0]["quat"]
    expected = glb.quat_multiply(glb._euler_to_quat(0, 45, 0),
                                 glb._euler_to_quat(90, 0, 0))
    assert got == pytest.approx(expected)


def test_a_child_is_carried_by_its_parents_position_and_rotation():
    scene = {
        "version": 2,
        "parts": [{
            "group": "g", "position": {"x": 2, "y": 0, "z": 0},
            "rotation": {"x": 0, "y": 90, "z": 0},
            "children": [_leaf(position={"x": 1, "y": 0, "z": 0})],
        }],
    }
    x, y, z = manifest.expand(scene)[0]["position"]
    # +X rotated 90 degrees about Y points along -Z
    assert (x, y, z) == pytest.approx((2.0, 0.0, -1.0), abs=1e-9)


# --------------------------------------------------------------------------
# 4. v1 is untouched
# --------------------------------------------------------------------------


def _close(got, want, path=""):
    """Recursive comparison with a tolerance, returning the first mismatch.

    Written out rather than reached for from a library because the failure
    message has to name WHERE — "the sculpture changed" is useless; "node 17's
    translation moved on y" is actionable.
    """
    if isinstance(want, dict):
        if not isinstance(got, dict) or set(got) != set(want):
            return f"{path}: keys differ"
        for key in want:
            bad = _close(got[key], want[key], f"{path}.{key}")
            if bad:
                return bad
    elif isinstance(want, list):
        if not isinstance(got, list) or len(got) != len(want):
            return f"{path}: length {len(got) if isinstance(got, list) else '?'} != {len(want)}"
        for i, item in enumerate(want):
            bad = _close(got[i], item, f"{path}[{i}]")
            if bad:
                return bad
    elif isinstance(want, bool) or not isinstance(want, (int, float)):
        if got != want:
            return f"{path}: {got!r} != {want!r}"
    elif abs(float(got) - float(want)) > TOLERANCE:
        return f"{path}: {got} != {want}"
    return None


def _summary(data):
    """What the file MEANS, in portable terms. Mirrors the fixture writer."""
    g = _gltf(data)
    return {
        "nodes": [
            {"name": n["name"], "mesh": n["mesh"],
             "translation": n.get("translation", [0.0, 0.0, 0.0]),
             "rotation": n.get("rotation", [0.0, 0.0, 0.0, 1.0])}
            for n in g["nodes"]
        ],
        "materials": g["materials"],
        "mesh_count": len(g["meshes"]),
        "vertex_counts": [
            g["accessors"][m["primitives"][0]["attributes"]["POSITION"]]["count"]
            for m in g["meshes"]
        ],
        "bounds": [[a["min"], a["max"]] for a in g["accessors"] if "min" in a],
        "triangles": sum(g["accessors"][p["indices"]]["count"] // 3
                         for m in g["meshes"] for p in m["primitives"]),
    }


def test_the_v1_fixture_is_not_empty():
    """A sweep over nothing is the same green as a sweep that found nothing."""
    fixture = json.loads(V1_FIXTURE.read_text(encoding="utf-8"))
    assert set(fixture) == {"lighthouse", "colonnade", "brazier"}
    assert sum(len(v["nodes"]) for v in fixture.values()) == 35


@pytest.mark.parametrize("name", ["lighthouse", "colonnade", "brazier"])
def test_a_v1_manifest_still_renders_the_same_sculpture(name):
    """The version number's entire promise. If this fails, every sculpture
    anyone exported before v2 has silently changed.

    Structural, not byte-wise — see V1_FIXTURE for why the byte version was
    wrong. Every node's placement, every material, every vertex and triangle
    count, and every mesh's bounding box, to a millionth of a metre.
    """
    fixture = json.loads(V1_FIXTURE.read_text(encoding="utf-8"))[name]
    got = _summary(manifest.render(_load(f"{name}.json"))[0])
    bad = _close(got, fixture, name)
    assert bad is None, bad


@pytest.mark.parametrize("name", ["lighthouse", "colonnade", "brazier", "cart"])
def test_rendering_is_deterministic_within_a_process(name):
    """The byte-identity that IS true and IS needed: export, re-import and
    re-render has to produce the same file, or the round trip on
    /scene-manifest is an approximation rather than an identity."""
    m = _load(f"{name}.json")
    first = manifest.render(m)[0]
    second = manifest.render(manifest.loads(manifest.dumps(m)))[0]
    assert hashlib.sha256(first).digest() == hashlib.sha256(second).digest()


def test_composing_with_the_identity_preserves_negative_zero():
    """A REGRESSION, and it cost an hour. Routing flat manifests through the
    expander rewrote a coordinate of -0.0 as 0.0, because `-0.0 + 0.0` is
    `+0.0` in IEEE arithmetic. Identical geometry, different bytes — and the
    v1 hash above is what caught it."""
    scene = {"version": 1, "parts": [_leaf(position={"x": -0.0, "y": 0.5, "z": 0})]}
    assert str(manifest.expand(scene)[0]["position"][0]) == "-0.0"


# --------------------------------------------------------------------------
# 5. The limits, and the refusals
# --------------------------------------------------------------------------


def test_the_part_limit_counts_LEAVES_after_expansion():
    """A ref costs its def's leaf count every time it is placed — which is what
    the renderer and the viewer actually carry."""
    scene = {
        "version": 2,
        "defs": {"pair": {"children": [_leaf(name="a"), _leaf(name="b")]}},
        "parts": [{"ref": "pair", "position": {"x": 0, "y": 0, "z": 0}}
                  for _ in range(sculptor.MAX_PARTS // 2 + 1)],
    }
    with pytest.raises(manifest.ManifestError, match="after expanding"):
        manifest.validate(scene)


@pytest.mark.parametrize("scene,expect", [
    ({"version": 2, "parts": [{"ref": "nope", "position": {"x": 0, "y": 0, "z": 0}}]},
     "not in defs"),
    ({"version": 2, "defs": {"a": {"children": [
        {"ref": "a", "position": {"x": 0, "y": 0, "z": 0}}]}},
      "parts": [{"ref": "a", "position": {"x": 0, "y": 0, "z": 0}}]},
     "contains itself"),
    ({"version": 2, "defs": {"a": {"children": []}},
      "parts": [{"ref": "a", "position": {"x": 0, "y": 0, "z": 0}}]},
     "renders nothing"),
    ({"version": 1, "parts": [], "defs": {}}, "version 1 has no defs"),
    ({"version": 2, "parts": [{"group": "g", "position": {"x": 0, "y": 0, "z": 0},
                               "children": [{"shape": "nope"}]}]},
     "missing"),
])
def test_the_refusals_name_what_is_wrong(scene, expect):
    with pytest.raises(manifest.ManifestError) as exc:
        manifest.validate(scene)
    assert expect in str(exc.value)


def test_a_def_with_a_position_is_refused_with_the_reason():
    """The most likely honest mistake: a def describes a thing, a ref says
    where it goes. Keeping position out is what makes sharing sound."""
    scene = {
        "version": 2,
        "defs": {"w": _leaf()},                       # _leaf() HAS a position
        "parts": [{"ref": "w", "position": {"x": 0, "y": 0, "z": 0}}],
    }
    with pytest.raises(manifest.ManifestError, match="a def has no position"):
        manifest.validate(scene)


def test_a_def_may_reference_one_declared_after_it():
    """Order in the file should not matter; refusing forward references would
    make a hand-edited manifest fragile for no reason."""
    style = {k: v for k, v in _leaf().items() if k != "position"}
    scene = {
        "version": 2,
        "defs": {
            "outer": {"children": [{"ref": "inner",
                                    "position": {"x": 0, "y": 0, "z": 0}}]},
            "inner": style,
        },
        "parts": [{"ref": "outer", "position": {"x": 0, "y": 0, "z": 0}}],
    }
    assert len(manifest.expand(scene)) == 1


# --------------------------------------------------------------------------
# 6. Round trip
# --------------------------------------------------------------------------


def test_a_nested_manifest_exports_byte_stably():
    """`dumps(loads(t)) == t` has to hold through defs and children too, or a
    nested manifest shows a diff every time it is saved."""
    for name in ("cart.json", "cart-flat.json"):
        text = (SAMPLES / name).read_text(encoding="utf-8")
        assert manifest.dumps(manifest.loads(text)) == text


def test_the_cart_is_the_instancing_sample_the_page_points_at():
    page = (REPO / "docs/scene-manifest/scene-manifest.md").read_text(encoding="utf-8")
    assert "cart.json" in page
