"""/model-upload — render a visitor's own `.glb`.

The owner's ask: "a seperate dcc.upload that accepts .gib file types and renders
their respective model on screen using the component".

WHAT IS WORTH TESTING is the refusals, not the happy path. A `.glb` that renders
is visible the moment you look at the page; a bad file that reaches the viewer
just silently fails to draw, and the visitor learns nothing. So every rule has a
case here, and each asserts the MESSAGE says which rule was broken.
"""

from __future__ import annotations

import base64
import importlib
import json
import pathlib
import struct

import pytest

from lib import glb, manifest, uploads

REPO = pathlib.Path(__file__).resolve().parent.parent
SAMPLES = REPO / "docs" / "scene-manifest" / "samples"


def _real_glb(name="brazier"):
    return manifest.render(
        manifest.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    )[0]


def _url(raw, media="model/gltf-binary"):
    return f"data:{media};base64," + base64.b64encode(raw).decode()


def _page():
    return importlib.import_module("docs.model-upload.model_upload")


# --------------------------------------------------------------------------
# Accepting a real file
# --------------------------------------------------------------------------


def test_a_real_glb_is_accepted_whatever_media_type_the_browser_guessed():
    """A `.glb` arrives as `model/gltf-binary` on a tidy machine and
    `application/octet-stream` on most. Trusting the label would refuse the
    majority of real uploads."""
    raw = _real_glb()
    for media in ("model/gltf-binary", "application/octet-stream", ""):
        got, message = uploads.decode_model(_url(raw, media), "thing.glb")
        assert got == raw, f"refused when the browser said {media!r}: {message}"
        assert "glTF 2.0" in message


def test_the_page_hands_the_viewer_the_uploaded_bytes():
    page = _page()
    raw = _real_glb()
    src, alt, status, facts, summary = page.show_model(_url(raw), "brazier.glb")

    assert src.startswith("data:"), "the viewer gets a data URL"
    assert base64.b64decode(src.split(",", 1)[1]) == raw, "and the same bytes"
    assert "brazier.glb" in alt, "the alt text names the file"
    assert "brazier.glb" in status
    assert summary["meshes"] == 5
    assert facts is not None


# --------------------------------------------------------------------------
# Every refusal names its rule
# --------------------------------------------------------------------------


@pytest.mark.parametrize("contents,filename,expect", [
    (None, None, ""),
    ("not-a-data-url", "x.glb", "not a data URL"),
    ("data:model/gltf-binary;base64,!!!!", "x.glb", "not valid base64"),
    (None, None, ""),
])
def test_malformed_uploads_are_named_not_swallowed(contents, filename, expect):
    _raw, message = uploads.decode_model(contents, filename)
    assert expect in message


def test_a_gltf_json_file_is_refused_with_the_reason_it_cannot_work():
    """The most likely honest mistake a visitor makes. A `.gltf` POINTS AT its
    buffers and textures, which were not uploaded with it, so it is refused
    with an explanation rather than drawn as an empty scene."""
    payload = json.dumps({"asset": {"version": "2.0"}}).encode()
    _raw, message = uploads.decode_model(_url(payload, "model/gltf+json"), "scene.gltf")
    assert "not a binary glTF" in message
    assert ".gltf" in message and "not work" in message


def test_a_renamed_file_of_another_kind_is_refused():
    _raw, message = uploads.decode_model(_url(b"PK\x03\x04zipzipzip"), "model.glb")
    assert "begins with the four bytes" in message


def test_glTF_version_1_is_refused_by_name():
    """A different format with a different chunk layout. Failing clearly beats
    handing the viewer something it will not draw."""
    body = b"glTF" + (1).to_bytes(4, "little") + (20).to_bytes(4, "little") + b"12345678"
    _raw, message = uploads.decode_model(_url(body), "old.glb")
    assert "version 1" in message


def test_a_truncated_file_is_caught_by_its_own_length_field():
    """THE CHECK WORTH HAVING. A GLB declares its total length in bytes 8-11, so
    a transfer that stopped early can be named instead of failing silently in
    the viewer."""
    raw = bytearray(_real_glb())
    truncated = bytes(raw[:len(raw) // 2])
    _got, message = uploads.decode_model(_url(truncated), "half.glb")
    assert "truncated" in message


def test_the_size_cap_is_measured_on_decoded_bytes():
    """base64 inflates by 4/3; measuring the encoded string would make the
    published cap wrong by a third — the same reasoning as the image cap."""
    raw = _real_glb()
    _got, message = uploads.decode_model(_url(raw), "big.glb", max_bytes=1000)
    assert "the cap is" in message
    assert f"{len(raw) / 1048576:.1f} MB" in message


def test_a_refusal_leaves_the_viewer_alone():
    """The model already on screen must survive a bad upload — replacing it
    with nothing would punish the visitor for a typo."""
    from dash import no_update

    page = _page()
    src, alt, status, facts, summary = page.show_model(_url(b"nope"), "bad.glb")
    assert src is no_update and alt is no_update
    assert facts is no_update and summary is no_update
    assert "not a binary glTF" in status


def test_a_glb_with_a_broken_json_chunk_does_not_raise_into_the_page():
    """Passes the header checks, fails to parse. The page must say so rather
    than 500."""
    from dash import no_update

    body = b"glTF" + (2).to_bytes(4, "little")
    chunk = b"{ this is not json"
    body += (12 + 8 + len(chunk)).to_bytes(4, "little")
    body += len(chunk).to_bytes(4, "little") + b"JSON" + chunk
    page = _page()
    src, _alt, status, _facts, _summary = page.show_model(_url(body), "broken.glb")
    assert src is no_update
    assert "malformed" in status


# --------------------------------------------------------------------------
# The readout says something true
# --------------------------------------------------------------------------


def test_the_summary_counts_what_the_gpu_will_draw():
    """Triangles are summed from the accessor behind each primitive's indices,
    so the number is the geometry in the file rather than a figure from an
    exporter's dialog."""
    raw = _real_glb()
    summary = glb.summarize(raw)

    length = struct.unpack("<I", raw[12:16])[0]
    gltf = json.loads(raw[20:20 + length])
    expected = sum(gltf["accessors"][p["indices"]]["count"] // 3
                   for m in gltf["meshes"] for p in m["primitives"])
    assert summary["triangles"] == expected > 0
    assert summary["meshes"] == len(gltf["meshes"])
    assert summary["bytes"] == len(raw)


def test_the_summary_reads_only_the_header_and_the_json_chunk():
    """So describing a 30 MB model costs what describing a 30 KB one costs.
    Asserted by truncating everything after the JSON chunk: if buffers were
    being read, this would fail."""
    raw = _real_glb()
    length = struct.unpack("<I", raw[12:16])[0]
    header_only = raw[:20 + length]
    assert len(header_only) < len(raw)
    assert glb.summarize(header_only)["triangles"] == glb.summarize(raw)["triangles"]


def test_a_textured_model_reports_its_texture():
    """The row that answers "is this model carrying its own imagery, or am I
    looking at flat material colour" — which is the question /texture-upload
    raises."""
    from lib import texture

    scene = manifest.loads((SAMPLES / "brazier.json").read_text(encoding="utf-8"))
    plain = glb.summarize(manifest.render(scene)[0])
    draped = glb.summarize(manifest.render(scene, texture_png=b"\x89PNG\r\n\x1a\n")[0])
    assert plain["textures"] == 0
    assert draped["textures"] == 1
    assert texture.MAX_TEXTURE_PX > 0


def test_every_row_the_table_renders_is_a_key_the_summary_provides():
    """The panel and the thing it describes must not drift."""
    page = _page()
    summary = glb.summarize(_real_glb())
    for _label, key, formatter in page.ROWS:
        assert key in summary, f"the table renders {key!r}, which is not measured"
        assert formatter(summary[key])


def test_the_page_writes_nothing_to_disk():
    source = (REPO / "docs/model-upload/model_upload.py").read_text(encoding="utf-8")
    for forbidden in ("write_bytes", "write_text", "mkdtemp", "NamedTemporary",
                      "os.makedirs", "shutil."):
        assert forbidden not in source


def test_the_cap_is_stated_on_the_page_and_matches_the_code():
    """A published number that disagrees with the enforced one is worse than no
    published number."""
    page_md = (REPO / "docs/model-upload/model-upload.md").read_text(encoding="utf-8")
    assert f"{uploads.MAX_MODEL_BYTES / 1048576:.0f} MB" in page_md
