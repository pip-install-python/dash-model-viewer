"""The glTF writer and both geometry pipelines — none of these call the API.

`conftest.py` blanks `ANTHROPIC_API_KEY`, so `sculptor.sculpt()` and
`relief.analyse()` take their no-key branches. Everything worth testing here is
either side of that call: the file format, the clamps, and the geometry.

The GLB assertions are deliberately structural rather than visual. A relief is
18 mm of depth on a 300 mm panel — flat-shaded from the front it looks like a
blank rectangle whether it worked or not, so "it renders" proves nothing. The
height distribution does.
"""

from __future__ import annotations

import json
import struct

import pytest

from lib import glb, relief, sculptor


def _parse(data: bytes):
    """Minimal GLB reader — deliberately not reusing the writer's own code."""
    magic, version, total = struct.unpack("<III", data[:12])
    assert magic == 0x46546C67, "not a GLB"
    assert version == 2
    assert total == len(data), "header length disagrees with the file"
    jlen, jtype = struct.unpack("<II", data[12:20])
    assert jtype == 0x4E4F534A, "first chunk is not JSON"
    gltf = json.loads(data[20:20 + jlen])
    blen, btype = struct.unpack("<II", data[20 + jlen:28 + jlen])
    assert btype == 0x004E4942, "second chunk is not BIN"
    return gltf, jlen, blen


# --------------------------------------------------------------------------
# The file format
# --------------------------------------------------------------------------


def test_a_minimal_glb_parses():
    data = glb.GLBBuilder().add(glb.box()).build()
    gltf, _, _ = _parse(data)
    assert gltf["asset"]["version"] == "2.0"
    assert len(gltf["meshes"]) == 1


def test_chunks_are_four_byte_aligned():
    """An unpadded chunk fails in three.js with an unhelpful error."""
    data = glb.GLBBuilder().add(glb.sphere()).add(glb.cone()).build()
    _, jlen, blen = _parse(data)
    assert jlen % 4 == 0
    assert blen % 4 == 0


def test_position_accessors_carry_min_and_max():
    """REQUIRED by the spec. Without it three.js computes no bounding box, so
    `model_info["dimensions"]` comes back as zeros and every camera-framing
    calculation collapses."""
    data = glb.GLBBuilder().add(glb.box(1, 2, 3)).build()
    gltf, _, _ = _parse(data)
    positions = [
        gltf["accessors"][p["attributes"]["POSITION"]]
        for mesh in gltf["meshes"] for p in mesh["primitives"]
    ]
    assert positions
    for acc in positions:
        assert "min" in acc and "max" in acc
        assert len(acc["min"]) == 3


def test_declared_bounds_match_the_requested_size():
    data = glb.GLBBuilder().add(glb.box(1.0, 2.0, 3.0)).build()
    gltf, _, _ = _parse(data)
    acc = gltf["accessors"][gltf["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]
    extent = [hi - lo for lo, hi in zip(acc["min"], acc["max"])]
    assert extent == pytest.approx([1.0, 2.0, 3.0])


def test_empty_build_refuses():
    with pytest.raises(ValueError):
        glb.GLBBuilder().build()


@pytest.mark.parametrize(
    "factory",
    [glb.box, glb.sphere, glb.cylinder, glb.cone, glb.torus, glb.plane],
)
def test_every_primitive_produces_valid_geometry(factory):
    mesh = factory()
    assert len(mesh.positions) >= 3
    assert len(mesh.indices) % 3 == 0
    assert max(mesh.indices) < len(mesh.positions), "index out of range"
    assert len(mesh.normals) == len(mesh.positions)
    data = glb.GLBBuilder().add(mesh).build()
    _parse(data)


def test_a_texture_becomes_an_image_and_sampler():
    png = _tiny_png()
    mat = glb.Material(texture_png=png, name="tex")
    data = glb.GLBBuilder().add(glb.plane(material=mat)).build()
    gltf, _, _ = _parse(data)
    assert len(gltf["images"]) == 1
    assert gltf["images"][0]["mimeType"] == "image/png"
    assert gltf["textures"][0]["sampler"] == 0
    assert "baseColorTexture" in gltf["materials"][0]["pbrMetallicRoughness"]


def _tiny_png() -> bytes:
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (200, 40, 40)).save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------
# Sculptor — text to primitives
# --------------------------------------------------------------------------


SCENE = {
    "parts": [
        {"name": "base", "shape": "cylinder",
         "size": {"x": 0.6, "y": 1.2, "z": 0.6},
         "position": {"x": 0, "y": 0.6, "z": 0},
         "rotation": {"x": 0, "y": 0, "z": 0},
         "color": "#A8A29A", "metallic": 0.0, "roughness": 0.8,
         "emissive_strength": 0.0},
    ]
}


def test_no_key_fails_closed_with_an_explanation():
    result = sculptor.sculpt("a lighthouse")
    assert result.ok is False
    assert "ANTHROPIC_API_KEY" in result.reason


def test_build_is_pure_and_deterministic():
    a, _, _ = sculptor.build(SCENE)
    b, _, _ = sculptor.build(SCENE)
    assert a == b, "same scene must give byte-identical output"


def test_part_budget_is_enforced_and_reported():
    scene = {"parts": [dict(SCENE["parts"][0]) for _ in range(sculptor.MAX_PARTS + 9)]}
    _, notes, used = sculptor.build(scene)
    assert used == sculptor.MAX_PARTS
    assert any("kept the first" in n for n in notes)


def test_unknown_shapes_are_dropped_with_a_note():
    scene = {"parts": [dict(SCENE["parts"][0], shape="dodecahedron"),
                       SCENE["parts"][0]]}
    _, notes, used = sculptor.build(scene)
    assert used == 1
    assert any("unknown shape" in n for n in notes)


def test_a_scene_with_nothing_usable_raises():
    with pytest.raises(ValueError):
        sculptor.build({"parts": [dict(SCENE["parts"][0], shape="nope")]})


def test_runaway_sizes_are_clamped():
    scene = {"parts": [dict(SCENE["parts"][0],
                            size={"x": 9999, "y": 9999, "z": 9999},
                            position={"x": 500, "y": 0, "z": 0})]}
    data, _, _ = sculptor.build(scene)
    gltf, _, _ = _parse(data)
    acc = gltf["accessors"][gltf["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]
    assert max(hi - lo for lo, hi in zip(acc["min"], acc["max"])) <= sculptor.MAX_EXTENT + 1e-6
    assert abs(gltf["nodes"][0]["translation"][0]) <= sculptor.MAX_SCENE_RADIUS


def test_hex_colour_is_converted_to_linear():
    """glTF baseColorFactor is LINEAR. Passing sRGB straight through renders
    every generated palette washed out — and it looks like a lighting bug."""
    mid = sculptor._colour("#808080")
    assert all(0.2 < c < 0.24 for c in mid), mid       # 0.5 sRGB -> ~0.216 linear
    assert sculptor._colour("#FFFFFF") == pytest.approx((1.0, 1.0, 1.0))
    assert sculptor._colour("not a colour") == (0.75, 0.75, 0.78)


def test_data_url_is_what_model_viewer_accepts():
    data, _, _ = sculptor.build(SCENE)
    url = sculptor.to_data_url(data)
    assert url.startswith("data:model/gltf-binary;base64,")
    import base64
    assert base64.b64decode(url.split(",", 1)[1]) == data


# --------------------------------------------------------------------------
# Relief — image to geometry
# --------------------------------------------------------------------------


def _gradient_png(w=64, h=64, light_background=True) -> bytes:
    """A dark disc on a light field — the classic cut_light case."""
    from PIL import Image, ImageDraw
    import io
    bg, fg = ((245, 245, 245), (40, 40, 40)) if light_background else ((20, 20, 20), (230, 230, 230))
    img = Image.new("RGB", (w, h), bg)
    ImageDraw.Draw(img).ellipse([w * 0.25, h * 0.25, w * 0.75, h * 0.75], fill=fg)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_carve_produces_a_parseable_glb_with_a_texture():
    data, stats = relief.carve(_gradient_png(), dict(relief.DEFAULT_PARAMS))
    gltf, _, _ = _parse(data)
    assert len(gltf["images"]) == 1, "the source image must ship as the texture"
    assert stats["triangles"] > 1000
    assert len(stats["size_m"]) == 3


def test_the_backdrop_is_cut_to_the_base_plate():
    """THE bug this parameter exists for: with brightness-as-height, a subject
    on white makes the BACKGROUND the tallest part and sinks the subject into
    it — the whole carving renders as a blank slab."""
    params = dict(relief.DEFAULT_PARAMS, background="cut_light", invert=True)
    data, _ = relief.carve(_gradient_png(light_background=True), params)
    gltf, jlen, _ = _parse(data)

    acc = gltf["accessors"][gltf["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]
    z_lo, z_hi = acc["min"][2], acc["max"][2]
    assert z_hi > 0, "nothing was raised"
    assert z_lo < 0, "there is no back plate"
    # A disc on a field: most of the surface must sit flat at the base.
    assert z_hi - z_lo > 0.001


def test_keep_and_cut_produce_different_geometry():
    image = _gradient_png(light_background=True)
    kept, _ = relief.carve(image, dict(relief.DEFAULT_PARAMS, background="keep"))
    cut, _ = relief.carve(image, dict(relief.DEFAULT_PARAMS, background="cut_light"))
    assert kept != cut, "the background parameter did nothing"


@pytest.mark.parametrize("profile", list(relief.PROFILES))
def test_every_profile_carves(profile):
    data, _ = relief.carve(_gradient_png(), dict(relief.DEFAULT_PARAMS,
                                                 depth_profile=profile))
    _parse(data)


def test_an_unknown_profile_falls_back_rather_than_raising():
    data, _ = relief.carve(_gradient_png(),
                           dict(relief.DEFAULT_PARAMS, depth_profile="chisel"))
    _parse(data)


def test_analysis_without_a_key_returns_defaults_and_says_so():
    params, notes = relief.analyse(_gradient_png(), "image/png")
    assert params["depth_profile"] in relief.PROFILES
    assert any("default" in n for n in notes)


def test_oversized_and_unsupported_uploads_are_refused():
    assert relief.relief_from_image(b"", "image/png").ok is False
    assert relief.relief_from_image(b"x" * (relief.MAX_UPLOAD_BYTES + 1),
                                    "image/png").ok is False
    assert relief.relief_from_image(_gradient_png(), "image/tiff").ok is False


def test_the_whole_path_works_with_no_key():
    """The model chooses settings; its absence must cost quality, not the
    feature. A user with no key still gets an object."""
    result = relief.relief_from_image(_gradient_png(), "image/png")
    assert result.ok is True
    assert result.data_url.startswith("data:model/gltf-binary;base64,")
    assert result.alt
    assert any("default" in n for n in result.notes)


# --------------------------------------------------------------------------
# The spend ceiling
# --------------------------------------------------------------------------


def test_spend_starts_open_and_closes_on_call_count(monkeypatch):
    from lib import spend

    spend.reset()
    monkeypatch.setattr(spend, "MAX_CALLS", 3)
    assert spend.check(1).allowed

    for _ in range(3):
        spend.record("claude-haiku-4-5", 1000, 1000)
    verdict = spend.check(1)
    assert verdict.allowed is False
    assert "Rate limit" in verdict.reason
    spend.reset()


def test_spend_closes_on_the_dollar_ceiling(monkeypatch):
    from lib import spend

    spend.reset()
    monkeypatch.setattr(spend, "MAX_SPEND_USD", 0.05)
    # Opus 5 output is $25/M, so 16k tokens is $0.40 — well over the ceiling.
    verdict = spend.check(1, spend.estimate_usd("claude-opus-5", 16000))
    assert verdict.allowed is False
    assert "Spend ceiling" in verdict.reason
    spend.reset()


def test_the_estimate_is_pessimistic():
    """It prices every call as if it used its whole budget — under-promising is
    the right bias for a number whose job is to stop an accident."""
    from lib import spend

    est = spend.estimate_usd("claude-opus-5", 4000)
    actual = spend.cost_usd("claude-opus-5", 1500, 2800)
    assert est > actual, (est, actual)


def test_sculpt_refuses_when_the_ceiling_is_reached(monkeypatch):
    """The gate must fire BEFORE the no-key branch, or a host with a key would
    spend past its ceiling while a host without one reports the wrong reason."""
    from lib import spend, sculptor

    spend.reset()
    monkeypatch.setattr(spend, "MAX_CALLS", 0)
    result = sculptor.sculpt("a lighthouse")
    assert result.ok is False
    assert "Rate limit" in result.reason
    spend.reset()


def test_effort_is_only_sent_to_models_that_accept_it():
    """Varying effort across a model that rejects it would run N identical
    calls and present them as a comparison — worse than an error."""
    from lib import spend

    assert "claude-haiku-4-5" not in spend.EFFORT_CAPABLE
    assert "claude-opus-5" in spend.EFFORT_CAPABLE


def test_measure_counts_triangles_and_the_palette():
    """Palette size is the benchmark's quality proxy, and it is read from the
    BUILT glb rather than the manifest — so a scene that claims one palette and
    builds another cannot game it."""
    scene = {"parts": [
        dict(SCENE["parts"][0], name="a", color="#FF0000"),
        dict(SCENE["parts"][0], name="b", color="#FF0000"),
        dict(SCENE["parts"][0], name="c", color="#00FF00"),
    ]}
    data, _, used = sculptor.build(scene)
    triangles, palette = sculptor.measure(scene, data)
    assert used == 3
    assert palette == 2, "two distinct colours across three parts"
    assert triangles > 0


# --------------------------------------------------------------------------
# Benchmark matrix
# --------------------------------------------------------------------------


def test_only_one_axis_varies_per_run():
    """Two moving variables make a comparison unreadable."""
    bm = pytest.importorskip("docs.benchmark.benchmark")

    by_model = bm._variants("model", ["low"], ["4000"],
                            ["claude-opus-5", "claude-haiku-4-5"],
                            "claude-opus-5", "low", 4000)
    assert {v[1] for v in by_model} == {"low"}
    assert {v[2] for v in by_model} == {4000}
    assert len({v[0] for v in by_model}) == 2

    by_effort = bm._variants("effort", ["low", "high"], ["4000"], [],
                             "claude-opus-5", "low", 4000)
    assert {v[0] for v in by_effort} == {"claude-opus-5"}
    assert len({v[1] for v in by_effort}) == 2


def test_the_matrix_is_capped():
    bm = pytest.importorskip("docs.benchmark.benchmark")
    variants = bm._variants("budget", [], ["2000", "4000", "8000", "16000"],
                            [], "claude-opus-5", "low", 4000)
    assert len(variants) <= bm.MAX_VARIANTS
