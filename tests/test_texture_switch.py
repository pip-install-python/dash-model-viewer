"""G6 — drape the uploaded image over the sculpture it produced.

The owner asked twice: "take the image used and … make it overlay on top of the
3d object", and then "i'd lean more to making it a dynamic switch as to make it
optional so that it can preview, include or just preview the texture on the
model".

THE PROPERTY THAT MATTERS is not "a texture appears". It is that ONE image lands
ONCE across the whole model — the naive implementation gives every primitive the
unit square and a thirty-part sculpture wears thirty copies of the photo — and
that turning the switch off leaves nothing behind.

NO MODEL IS CALLED ANYWHERE IN THIS FILE. Every case runs off a committed sample
manifest and a generated image, which is also the claim the page makes: the
switch is walkable on a host with no API key.
"""

from __future__ import annotations

import base64
import io
import json
import os
import pathlib
import struct

import pytest

from lib import glb, manifest, texture

REPO = pathlib.Path(__file__).resolve().parent.parent
SAMPLES = REPO / "docs" / "scene-manifest" / "samples"


def _image(width=800, height=600, noise=False):
    from PIL import Image

    if noise:
        img = Image.frombytes("RGB", (width, height), os.urandom(width * height * 3))
    else:
        img = Image.new("RGB", (width, height), (30, 90, 160))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def _data_url(raw):
    return "data:image/png;base64," + base64.b64encode(raw).decode()


def _gltf(data: bytes):
    """The JSON chunk of a .glb, so assertions are about the FILE."""
    length = struct.unpack("<I", data[12:16])[0]
    return json.loads(data[20:20 + length])


def _sample(name="colonnade"):
    return manifest.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def _page():
    import importlib

    return importlib.import_module("docs.sculpt-from-image.sculpt_from_image")


def _download(page, clicks, stored, mode, image):
    """save_glb returns (payload, message, hide) — it gained the message
    outputs so a refused build is SHOWN instead of swallowed. Tests about the
    file take the payload; the message has its own test."""
    payload, _message, _hide = page.save_glb(clicks, stored, mode, image)
    return payload


# --------------------------------------------------------------------------
# One image, once
# --------------------------------------------------------------------------


def test_one_image_is_embedded_ONCE_however_many_parts_wear_it():
    """THE TEST THAT MAKES THE FEATURE POSSIBLE. 28 parts sharing a photo must
    not embed 28 photos: with a realistic (incompressible) image that is ~22 MB
    against a 3,000,000-byte ceiling. Deduped on the texture BYTES in
    lib/glb.py."""
    png = texture.prepare(_image(noise=True))
    data, _notes, used = manifest.render(_sample(), texture_png=png)
    gltf = _gltf(data)

    assert used == 28, "the sample is the 28-part one, or this proves little"
    assert len(gltf["images"]) == 1, f"{len(gltf['images'])} copies of the image"
    assert len(gltf["textures"]) == 1
    assert len(gltf["materials"]) == 28, "each part still has its own material"
    assert all("baseColorTexture" in m["pbrMetallicRoughness"]
               for m in gltf["materials"])
    assert len(data) < 3_000_000


def test_every_part_carries_texture_coordinates():
    png = texture.prepare(_image())
    gltf = _gltf(manifest.render(_sample(), texture_png=png)[0])
    for mesh in gltf["meshes"]:
        for primitive in mesh["primitives"]:
            assert "TEXCOORD_0" in primitive["attributes"], (
                f"{mesh['name']} has no UVs — it would render untextured"
            )


def test_the_projection_spans_the_model_rather_than_repeating_per_part():
    """A part on the left takes the left of the picture. If each primitive got
    the unit square, both parts would span 0..1 and this would fail."""
    left = glb.box(0.5, 0.5, 0.5, material=glb.Material(), translation=(-2, 0, 0))
    right = glb.box(0.5, 0.5, 0.5, material=glb.Material(), translation=(2, 0, 0))
    texture.drape([left, right], b"x")

    assert max(u for u, _v in left.uvs) < min(u for u, _v in right.uvs), (
        "the two parts overlap in u — the image is repeating, not projecting"
    )
    assert min(u for u, _v in left.uvs) == pytest.approx(0.0)
    assert max(u for u, _v in right.uvs) == pytest.approx(1.0)


def test_the_picture_is_not_upside_down():
    """glTF's texture origin is the image's UPPER-left, so the TOP of the model
    must take v=0. Getting this backwards is invisible to every other
    assertion here and obvious to anyone looking at the page."""
    low = glb.box(0.5, 0.5, 0.5, material=glb.Material(), translation=(0, -2, 0))
    high = glb.box(0.5, 0.5, 0.5, material=glb.Material(), translation=(0, 2, 0))
    texture.drape([low, high], b"x")

    assert max(v for _u, v in high.uvs) < min(v for _u, v in low.uvs)
    assert min(v for _u, v in high.uvs) == pytest.approx(0.0), "top of the image"


def test_a_flat_model_does_not_divide_by_zero():
    flat = glb.plane(2.0, 2.0, material=glb.Material())
    assert texture.drape([flat], b"x") == 1
    assert all(0.0 <= u <= 1.0 and 0.0 <= v <= 1.0 for u, v in flat.uvs)


# --------------------------------------------------------------------------
# The switch leaves nothing behind
# --------------------------------------------------------------------------


def test_include_then_off_is_byte_identical_to_never_textured():
    """ops' acceptance. The switch has to be a switch, not a one-way door."""
    scene = _sample()
    never = manifest.render(scene)[0]
    manifest.render(scene, texture_png=texture.prepare(_image()))
    back_off = manifest.render(scene)[0]
    assert back_off == never


def test_draping_does_not_touch_the_manifest():
    """The manifest stays TEXTURELESS by design, so its bytes say the same
    thing whether or not it was ever draped — which is what keeps a saved
    manifest a stable, diffable record."""
    scene = _sample()
    before = manifest.dumps(scene)
    manifest.render(scene, texture_png=texture.prepare(_image()))
    assert manifest.dumps(scene) == before
    assert "texture" not in before.lower()


def test_a_draped_part_can_actually_BE_SEEN():
    """THE BUG THE OWNER FOUND, as a regression.

    I shipped this preserving each part's `metallic`, on the argument that it
    made the trade-off narrower than replacing the whole surface. That argument
    is physically wrong: in metallic-roughness PBR the diffuse term is
    `baseColor x (1 - metallic)`, so a part at 0.8 shows a fifth of the picture
    and a part at 1.0 shows none of it — the base colour stops being albedo and
    becomes a mirror's specular tint. The prompt asks models for "metallic near
    1.0 with roughness under 0.3" for anything gold or polished, so real
    sculptures reliably contain parts where the texture was simply invisible.

    Asserted on the MATERIALS IN THE FILE, not on the inputs, because that is
    what the renderer reads.
    """
    scene = _sample("brazier")
    draped = _gltf(manifest.render(scene, texture_png=texture.prepare(_image()))[0])

    assert any(p.get("metallic", 0) >= 0.4 for p in scene["parts"]), (
        "this sample must contain a shiny part, or it proves nothing"
    )
    for material in draped["materials"]:
        pbr = material["pbrMetallicRoughness"]
        assert pbr["baseColorFactor"] == [1.0, 1.0, 1.0, 1.0]
        assert pbr["metallicFactor"] == 0.0, (
            f"{material['name']} is {pbr['metallicFactor']} metallic while "
            f"draped — the picture is suppressed by that factor"
        )
        assert pbr["roughnessFactor"] >= texture.MIN_DRAPED_ROUGHNESS, (
            f"{material['name']} is near-mirror while draped — it shows the "
            f"environment rather than the photograph"
        )


def test_a_glowing_part_still_glows_while_draped():
    """The one surface property deliberately left alone. Emissive ADDS light on
    top of the shaded surface rather than replacing albedo, so it does not
    suppress the picture the way metallic does."""
    scene = _sample("brazier")
    plain = _gltf(manifest.render(scene)[0])["materials"]
    draped = _gltf(manifest.render(scene, texture_png=texture.prepare(_image()))[0])["materials"]

    assert any("emissiveFactor" in m for m in plain), "the sample must have a glow"
    for before, after in zip(plain, draped):
        assert after.get("emissiveFactor") == before.get("emissiveFactor")


# --------------------------------------------------------------------------
# What the page does with it
# --------------------------------------------------------------------------


def test_preview_shows_the_texture_but_downloads_without_it():
    """The one rule that stops the file quietly differing from the screen."""
    page = _page()
    scene = _sample()
    image = _data_url(_image())

    src, note, label = page.retexture("preview", scene, image)
    assert src.startswith("data:model/gltf-binary;base64,")
    # THE ASSERTION THIS TEST WAS MISSING. It checked only that a data URL came
    # back, so it passed while the picture was invisible on screen. "A render
    # happened" is not "the render is textured".
    shown = _gltf(base64.b64decode(src.split(",", 1)[1]))
    assert len(shown["images"]) == 1, "preview must actually show the texture"
    assert all(m["pbrMetallicRoughness"]["metallicFactor"] == 0.0
               for m in shown["materials"]), "and show it visibly"
    assert "untextured" in label, "the button must say what it will hand over"
    assert "untextured" in note

    payload = _download(page, 1, scene, "preview", image)
    assert base64.b64decode(payload["content"]) == manifest.render(scene)[0]
    assert payload["filename"].endswith(".glb")
    assert "-textured" not in payload["filename"]


def test_include_bakes_the_image_into_the_download():
    page = _page()
    scene = _sample()
    image = _data_url(_image())

    payload = _download(page, 1, scene, "include", image)
    data = base64.b64decode(payload["content"])
    assert data != manifest.render(scene)[0]
    assert len(_gltf(data)["images"]) == 1
    assert payload["filename"].endswith("-textured.glb"), (
        "the filename should distinguish it from the plain export"
    )


def test_off_downloads_exactly_what_item_2_shipped():
    page = _page()
    scene = _sample()
    payload = _download(page, 1, scene, "off", _data_url(_image()))
    assert base64.b64decode(payload["content"]) == manifest.render(scene)[0]


def test_the_switch_says_what_it_needs_when_it_has_nothing():
    page = _page()
    src, note, _label = page.retexture("include", None, None)
    assert src is not None  # no_update
    assert "Sculpt something" in note

    _src, note, _label = page.retexture("include", _sample(), None)
    assert "Upload an image" in note


def test_a_corrupt_upload_leaves_the_page_standing():
    """A texture that cannot be prepared must not take down a sculpture that
    is perfectly fine to look at untextured."""
    page = _page()
    scene = _sample()
    for bad in (None, "", "data:image/png;base64,!!!!", _data_url(b"not a png")):
        src, _note, _label = page.retexture("include", scene, bad)
        assert src is not None
        payload = _download(page, 1, scene, "include", bad)
        assert base64.b64decode(payload["content"]) == manifest.render(scene)[0], (
            "an unusable image must fall back to the plain sculpture"
        )


def test_a_new_sculpt_keeps_the_chosen_setting():
    """`si-manifest` is an Input to the re-render, not a State, so a fresh
    sculpt arrives draped if the switch is on rather than silently reverting."""
    import inspect

    # getsource on a decorated callback includes its @callback block, so the
    # wiring can be read straight off the function rather than parsed out of
    # the file.
    source = inspect.getsource(_page().retexture)
    assert 'Input("si-manifest", "data")' in source
    assert 'Input("si-texture", "value")' in source
    assert 'State("si-manifest"' not in source, (
        "as a State, a fresh sculpt would render untextured with the switch on"
    )


# --------------------------------------------------------------------------
# Walkable with no key at all
# --------------------------------------------------------------------------


def test_the_whole_switch_works_with_no_api_key():
    """The page's claim, asserted: a bundled manifest plus an uploaded image
    bakes and downloads on a host that cannot call a model."""
    for name in ("CHATGPT_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        assert not os.environ.get(name), f"{name} is set — this proves nothing"

    page = _page()
    payload = _download(page, 1, _sample("lighthouse"), "include",
                        _data_url(_image()))
    assert base64.b64decode(payload["content"])[:4] == b"glTF"


def test_the_texture_is_downscaled_under_the_cap():
    from PIL import Image

    prepared = texture.prepare(_image(2400, 1800, noise=True))
    with Image.open(io.BytesIO(prepared)) as img:
        assert max(img.size) <= texture.MAX_TEXTURE_PX
        assert img.format == "PNG"


def test_the_texture_cap_matches_the_other_page_that_bakes_one():
    """Two features embed an image in a .glb under the same ceiling. Two
    different answers is how one cap silently becomes two."""
    from lib import relief

    assert texture.MAX_TEXTURE_PX == relief.TEXTURE_PX
