"""The manifest contract: round-trip identity, refusals, and safe filenames.

Each prose pin in `test_scene_manifest_page.py` has a behaviour test here that
carries the claim. A page assertion on its own is decorative; the pair is what
makes the page's promise true. The pairs are named in the docstrings.
"""

from __future__ import annotations

import json
import math
import pathlib
import struct

import pytest

from lib import manifest, sculptor
from lib.glb import _euler_to_quat

REPO = pathlib.Path(__file__).resolve().parent.parent
SAMPLES = REPO / "docs" / "scene-manifest" / "samples"
SAMPLE_FILES = ["lighthouse.json", "colonnade.json", "brazier.json",
                "cart.json", "cart-flat.json"]
FIXTURE = SAMPLES / "INVALID-fixture.json"


def _part(**kw):
    p = {
        "name": "p", "shape": "box",
        "size": {"x": 0.4, "y": 0.4, "z": 0.4},
        "position": {"x": 0.0, "y": 0.2, "z": 0.0},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
        "color": "#C8A24B", "metallic": 0.1,
        "roughness": 0.6, "emissive_strength": 0.0,
    }
    p.update(kw)
    return p


def _manifest(**kw):
    m = {"version": 1, "name": "Test", "parts": [_part()]}
    m.update(kw)
    return m


# --------------------------------------------------------------------------
# The bundled samples are the importer's positive control
# --------------------------------------------------------------------------


def test_there_are_samples_to_test():
    """Note 194: a sweep over nothing is the same green as a sweep that found
    nothing. Assert the corpus before trusting anything below it."""
    assert SAMPLES.is_dir()
    found = sorted(p.name for p in SAMPLES.glob("*.json"))
    assert found == sorted(SAMPLE_FILES + ["INVALID-fixture.json"]), found


@pytest.mark.parametrize("name", SAMPLE_FILES)
def test_every_sample_validates_and_renders(name):
    m = manifest.loads((SAMPLES / name).read_text(encoding="utf-8"))
    data, _notes, used = manifest.render(m)
    # LEAVES, not top-level entries: in v2 one `ref` to a four-part assembly
    # is four parts drawn, and comparing against `len(m["parts"])` would make
    # a nested sample look like it had lost pieces.
    assert used == len(manifest.expand(m))
    assert data[:4] == b"glTF", "output is not a GLB"


def test_the_pages_example_IS_the_sample_file():
    """Pairs with test_the_page_exists_and_is_not_empty.

    The page's JSON block and the committed fixture are the same bytes, so the
    example a reader copies cannot drift from the file the importer is tested
    against.
    """
    page = (REPO / "docs" / "scene-manifest" / "scene-manifest.md").read_text(
        encoding="utf-8"
    )
    block = page.split("```json\n", 1)[1].split("```", 1)[0]
    assert block == (SAMPLES / "lighthouse.json").read_text(encoding="utf-8")


def test_the_big_sample_is_EXACTLY_the_part_limit():
    """The inclusive bound, proven on the wire rather than only in a test. The
    29th part lives in `test_one_part_over_the_limit_is_refused`."""
    m = json.loads((SAMPLES / "colonnade.json").read_text(encoding="utf-8"))
    assert len(m["parts"]) == sculptor.MAX_PARTS


def test_the_refusal_fixture_is_actually_refused():
    """A fixture that validated would make the page's refusal message a
    fabrication."""
    with pytest.raises(manifest.ManifestError) as exc:
        manifest.loads(FIXTURE.read_text(encoding="utf-8"))
    assert "emissive_strength" in str(exc.value)


def test_the_fixture_is_named_so_nobody_mistakes_it_for_a_sample():
    assert FIXTURE.name.startswith("INVALID")


# --------------------------------------------------------------------------
# Round-trip identity — the page's two equations
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", SAMPLE_FILES)
def test_export_of_import_is_byte_identical(name):
    """`export(import(m)) == m`. Pairs with the page's byte-stable claim."""
    text = (SAMPLES / name).read_text(encoding="utf-8")
    assert manifest.dumps(manifest.loads(text)) == text


@pytest.mark.parametrize("name", SAMPLE_FILES)
def test_import_of_export_renders_identical_bytes(name):
    """`import(export(scene))` renders byte-identical `.glb`."""
    m = manifest.loads((SAMPLES / name).read_text(encoding="utf-8"))
    first, _, _ = manifest.render(m)
    second, _, _ = manifest.render(manifest.loads(manifest.dumps(m)))
    assert first == second


def test_export_is_stable_across_key_order():
    """Two manifests differing only in key order export identically — which is
    what makes a diff of two exports show only what changed."""
    a = {"version": 1, "name": "X", "parts": [_part()]}
    b = {"parts": [dict(reversed(list(_part().items())))], "name": "X", "version": 1}
    assert manifest.dumps(a) == manifest.dumps(b)


def test_version_is_the_first_key_on_export():
    """Plain sort_keys would put it last, after name/notes/parts/provenance."""
    text = manifest.dumps(_manifest(notes="n", provenance={"model": "m"}))
    assert text.splitlines()[1].strip().startswith('"version"')


def test_export_ends_with_a_newline():
    assert manifest.dumps(_manifest()).endswith("}\n")


# --------------------------------------------------------------------------
# provenance is never read — the asymmetry, made a property
# --------------------------------------------------------------------------


def test_render_is_byte_identical_with_and_without_provenance():
    """Pairs with test_provenance_is_documented_as_never_read.

    The page says the renderer never reads it. This is that claim as a
    measurement rather than a sentence.
    """
    with_prov = _manifest(provenance={
        "prompt": "a tower", "model": "claude-opus-5",
        "usd": 0.0871, "generated": "2026-09-12",
    })
    without = _manifest()
    assert manifest.render(with_prov)[0] == manifest.render(without)[0]


def test_provenance_is_optional():
    assert manifest.validate(_manifest()) is not None


@pytest.mark.parametrize("bad,expect", [
    ({"cost": 1}, "provenance.cost"),
    ({"usd": "free"}, "provenance.usd"),
    ({"usd": -1}, "negative"),
    ({"generated": "12/09/2026"}, "ISO 8601"),
    ({"model": 5}, "provenance.model"),
])
def test_unknown_or_wrong_provenance_is_refused(bad, expect):
    """Strictness one level down. Without it, the escape hatch the top level
    closes reopens inside provenance."""
    with pytest.raises(manifest.ManifestError) as exc:
        manifest.validate(_manifest(provenance=bad))
    assert expect in str(exc.value)


# --------------------------------------------------------------------------
# Refusals, one per rule, each naming the field and its PATH
# --------------------------------------------------------------------------


def test_an_unknown_version_is_refused_and_not_partially_read():
    """Pairs with test_the_page_says_an_unknown_version_is_not_partially_read.

    The example is version 3 now that 2 is read. The property is unchanged and
    is the reason the number exists: a manifest from a build that knows more
    than this one is refused whole, never read for the parts it recognises.
    """
    with pytest.raises(manifest.ManifestError) as exc:
        manifest.validate({"version": 3, "parts": []})
    message = str(exc.value)
    assert "version 3" in message and "version 1 and 2" in message
    assert "not read partially" in message


def test_version_2_is_read_and_version_1_is_still_read():
    assert manifest.READS == (1, 2)
    assert manifest.VERSION == 2, "the highest this build understands"
    assert manifest.FLAT_VERSION == 1, "what a flat scene is stamped with"


def test_a_missing_version_is_refused():
    with pytest.raises(manifest.ManifestError, match="version: missing"):
        manifest.validate({"parts": []})


@pytest.mark.parametrize("bad,path", [
    ({"nope": 1}, "nope"),
    ({"parts": [_part(extra=1)]}, "parts[0].extra"),
])
def test_an_unknown_key_is_refused_WITH_ITS_PATH(bad, path):
    """Pairs with test_the_page_says_unknown_keys_are_REJECTED.

    The path matters more after part groups land: a nested unknown is the
    common case, and "unknown key" without a location is not actionable.
    """
    with pytest.raises(manifest.ManifestError) as exc:
        manifest.validate(_manifest(**bad))
    assert path in str(exc.value)


def test_an_unknown_shape_is_refused_by_name():
    with pytest.raises(manifest.ManifestError) as exc:
        manifest.validate(_manifest(parts=[_part(shape="dodecahedron")]))
    assert "dodecahedron" in str(exc.value)
    assert "parts[0].shape" in str(exc.value)


def test_a_size_over_the_extent_is_refused_with_the_bound():
    with pytest.raises(manifest.ManifestError) as exc:
        manifest.validate(_manifest(parts=[_part(size={"x": 40, "y": 1, "z": 1})]))
    assert "parts[0].size.x" in str(exc.value)
    assert str(sculptor.MAX_EXTENT) in str(exc.value)


def test_one_part_over_the_limit_is_refused():
    too_many = [_part() for _ in range(sculptor.MAX_PARTS + 1)]
    with pytest.raises(manifest.ManifestError) as exc:
        manifest.validate(_manifest(parts=too_many))
    assert str(sculptor.MAX_PARTS) in str(exc.value)


def test_exactly_the_limit_is_accepted():
    """The bound is inclusive; a test that only checks the refusal cannot tell
    an inclusive bound from an exclusive one."""
    assert manifest.validate(
        _manifest(parts=[_part() for _ in range(sculptor.MAX_PARTS)])
    )


@pytest.mark.parametrize("field", ["metallic", "roughness", "emissive_strength"])
def test_a_string_where_a_number_goes_is_refused(field):
    with pytest.raises(manifest.ManifestError) as exc:
        manifest.validate(_manifest(parts=[_part(**{field: "shiny"})]))
    assert f"parts[0].{field}" in str(exc.value)
    assert "expected a number" in str(exc.value)


def test_a_bool_is_not_accepted_as_a_number():
    """`isinstance(True, int)` is True in Python, so this needs its own guard."""
    with pytest.raises(manifest.ManifestError):
        manifest.validate(_manifest(parts=[_part(metallic=True)]))


@pytest.mark.parametrize("colour", ["red", "#FFF", "FFC15E", "#GGGGGG"])
def test_a_bad_colour_is_refused(colour):
    with pytest.raises(manifest.ManifestError, match="color"):
        manifest.validate(_manifest(parts=[_part(color=colour)]))


def test_an_emissive_strength_over_one_is_refused():
    """The draft of the page said ">= 0" and its own example used 3.0. The code
    clamps 0-1, so the page was wrong and the example would have been silently
    clamped."""
    with pytest.raises(manifest.ManifestError) as exc:
        manifest.validate(_manifest(parts=[_part(emissive_strength=3.0)]))
    assert "0.0 to 1.0" in str(exc.value)


def test_oversize_json_is_refused_before_parsing():
    huge = " " * (manifest.MAX_JSON_BYTES + 1)
    with pytest.raises(manifest.ManifestError, match="cap is"):
        manifest.loads(huge)


def test_invalid_json_is_refused_not_raised_as_a_decode_error():
    with pytest.raises(manifest.ManifestError, match="not valid JSON"):
        manifest.loads("{not json")


# --------------------------------------------------------------------------
# Rotation order — the quaternion, pinned
# --------------------------------------------------------------------------


def _node_rotation(data: bytes):
    """Pull the first node's quaternion out of a GLB's JSON chunk."""
    length = struct.unpack("<I", data[12:16])[0]
    gltf = json.loads(data[20:20 + length].decode("utf-8"))
    return gltf["nodes"][0].get("rotation")


@pytest.mark.parametrize("euler,expected", [
    ((90, 0, 0), [0.7071067811865476, 0.0, 0.0, 0.7071067811865476]),
    ((0, 90, 0), [0.0, 0.7071067811865476, 0.0, 0.7071067811865476]),
])
def test_a_single_axis_rotation_reaches_the_GLB_node(euler, expected):
    """Pairs with the page's Rotation order section."""
    rx, ry, rz = euler
    m = _manifest(parts=[_part(rotation={"x": rx, "y": ry, "z": rz})])
    got = _node_rotation(manifest.render(m)[0])
    assert got is not None, "the rotation never reached the node"
    for a, b in zip(got, expected):
        assert abs(a - b) < 1e-9, (got, expected)


def test_the_euler_order_is_Rz_Ry_Rx_as_the_page_states():
    """Measured, not asserted: compose the single-axis quaternions both ways
    and show which one the code agrees with. The page says extrinsic XYZ —
    X first about fixed axes — which is Rz · Ry · Rx."""
    def axis(which, deg):
        h = math.radians(deg) / 2
        s, c = math.sin(h), math.cos(h)
        return [s if which == "x" else 0, s if which == "y" else 0,
                s if which == "z" else 0, c]

    def qmul(a, b):
        ax, ay, az, aw = a
        bx, by, bz, bw = b
        return [aw * bx + ax * bw + ay * bz - az * by,
                aw * by - ax * bz + ay * bw + az * bx,
                aw * bz + ax * by - ay * bx + az * bw,
                aw * bw - ax * bx - ay * by - az * bz]

    got = _euler_to_quat(30, 40, 50)
    zyx = qmul(axis("z", 50), qmul(axis("y", 40), axis("x", 30)))
    xyz = qmul(axis("x", 30), qmul(axis("y", 40), axis("z", 50)))
    assert all(abs(a - b) < 1e-12 for a, b in zip(got, zyx)), "not Rz·Ry·Rx"
    assert not all(abs(a - b) < 1e-12 for a, b in zip(got, xyz)), (
        "Rx·Ry·Rz also matches — this test cannot tell the orders apart"
    )


# --------------------------------------------------------------------------
# Filenames — derived, never raw
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name,expected", [
    ("Lighthouse", "lighthouse.glb"),
    ("../../etc/passwd", "etc-passwd.glb"),
    ("", "sculpture.glb"),
    ("   ", "sculpture.glb"),
    ("!!!", "sculpture.glb"),
    ("A Tower / Mk2", "a-tower-mk2.glb"),
])
def test_the_filename_is_derived_and_safe(name, expected):
    assert manifest.filename({"version": 1, "parts": [], "name": name}, "glb") == expected


def test_a_very_long_name_is_capped():
    out = manifest.filename({"version": 1, "parts": [], "name": "x" * 400}, "glb")
    assert len(out) <= 56, out
    assert out.endswith(".glb")


@pytest.mark.parametrize("name", ["../x", "..", "/etc/passwd", "a\x00b", "a/b/c"])
def test_no_filename_can_contain_a_path_separator(name):
    out = manifest.filename({"version": 1, "parts": [], "name": name}, "glb")
    assert "/" not in out and "\\" not in out and ".." not in out, out


# --------------------------------------------------------------------------
# Nothing is stored — pairs with test_the_page_states_the_no_store_rule
# --------------------------------------------------------------------------


def test_the_manifest_module_writes_nothing_to_disk():
    source = (REPO / "lib" / "manifest.py").read_text(encoding="utf-8")
    for forbidden in ("open(", "write_text", "write_bytes", "mkdtemp",
                      "NamedTemporary", "os.makedirs"):
        assert forbidden not in source, f"{forbidden!r} appears in lib/manifest.py"
