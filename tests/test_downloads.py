"""Item 2: exporting what was generated, so it can be kept and reused.

The property worth testing is not "a button returns bytes" — it is the LOOP:
generate, save the manifest, re-import it, and get the same sculpture without
paying a model. That is what makes the export worth having rather than a file
you can only look at.
"""

from __future__ import annotations

import base64
import importlib
import pathlib

import pytest

from lib import build_stream, manifest

REPO = pathlib.Path(__file__).resolve().parent.parent

#: (module, poll args after the run id) — in the order the CALLBACK wires
#: them, model then text. Calling the function in its own order was how a
#: transposed signature on /generative-3d survived this suite: the
#: provenance came out inverted on the page and correct here. See
#: tests/test_callback_wiring.py.
PAGES = {
    "g3": ("docs.generative-3d.sculptor", ("claude-opus-5", "a lighthouse")),
    "si": ("docs.sculpt-from-image.sculpt_from_image", ("claude-opus-5", "the arches")),
}

SCENE = {
    "name": "Lighthouse",
    "notes": "a tapered tower",
    "parts": [{
        "name": "tower", "shape": "cylinder",
        "size": {"x": 0.4, "y": 2.0, "z": 0.4},
        "position": {"x": 0, "y": 1.0, "z": 0},
        "rotation": {"x": 0, "y": 0, "z": 0},
        "color": "#E8E4DC", "metallic": 0.0,
        "roughness": 0.8, "emissive_strength": 0.0,
    }],
}


def _finished(prefix):
    """Drive a page's poll to completion and return (module, stored manifest)."""
    module, args = PAGES[prefix]
    page = importlib.import_module(module)
    run = build_stream.new_run()
    build_stream.emit(run, {
        "phase": "done", "total": 1, "data_url": "data:model/gltf-binary;base64,ZZZ",
        "manifest": SCENE, "notes": [], "part_count": 1,
        "seconds": 12.0, "usd": 0.0432,
    })
    build_stream.finish(run, ok=True)
    # Located by SHAPE, not by index. This was `[-3]`, and adding one output
    # to the poll silently moved it onto a boolean — an index into a
    # 14-tuple is a test that breaks when the code is merely extended.
    returned = page.poll(1, run, *args)
    stored = next(v for v in returned if isinstance(v, dict) and "parts" in v)
    return page, stored


# --------------------------------------------------------------------------
# The loop
# --------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", PAGES)
def test_a_finished_build_stores_a_valid_versioned_manifest(prefix):
    _page, stored = _finished(prefix)
    assert stored["version"] == manifest.VERSION
    assert manifest.validate(stored) is not None


@pytest.mark.parametrize("prefix", PAGES)
def test_the_exported_manifest_re_renders_the_SAME_bytes(prefix):
    """THE POINT OF ITEM 2. Export, re-import, and the sculpture is identical —
    so the file is a way back to the object, not a souvenir."""
    page, stored = _finished(prefix)
    exported = page.save_manifest(1, stored)["content"]
    glb_now = base64.b64decode(page.save_glb(1, stored)["content"])
    glb_from_file, _notes, _used = manifest.render(manifest.loads(exported))
    assert glb_from_file == glb_now


@pytest.mark.parametrize("prefix", PAGES)
def test_the_glb_download_is_a_real_glb(prefix):
    page, stored = _finished(prefix)
    payload = page.save_glb(1, stored)
    assert payload["base64"] is True
    raw = base64.b64decode(payload["content"])
    assert raw[:4] == b"glTF"
    assert payload["filename"] == "lighthouse.glb"


@pytest.mark.parametrize("prefix", PAGES)
def test_the_manifest_download_is_byte_stable(prefix):
    page, stored = _finished(prefix)
    first = page.save_manifest(1, stored)["content"]
    second = page.save_manifest(2, stored)["content"]
    assert first == second
    assert first == manifest.dumps(manifest.loads(first))


# --------------------------------------------------------------------------
# Provenance is recorded, and is honest
# --------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", PAGES)
def test_the_stored_manifest_carries_real_provenance(prefix):
    """The prompt is the thing a user cannot reconstruct, so it is kept —
    and the cost, so a file says what it was worth."""
    _page, stored = _finished(prefix)
    p = stored["provenance"]
    assert p["model"] == "claude-opus-5"
    assert p["usd"] == 0.0432
    assert p["prompt"]
    assert len(p["generated"]) == 10, "an ISO 8601 date"


@pytest.mark.parametrize("prefix", PAGES)
def test_provenance_does_not_change_the_sculpture(prefix):
    """Pairs with the page's claim that the renderer never reads it."""
    _page, stored = _finished(prefix)
    without = {k: v for k, v in stored.items() if k != "provenance"}
    assert manifest.render(stored)[0] == manifest.render(without)[0]


# --------------------------------------------------------------------------
# Nothing downloads when there is nothing to download
# --------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", PAGES)
def test_no_download_before_a_build(prefix):
    from dash import no_update

    page, _stored = _finished(prefix)
    assert page.save_manifest(1, None) is no_update
    assert page.save_glb(1, None) is no_update


@pytest.mark.parametrize("prefix", PAGES)
def test_a_corrupt_store_does_not_raise_into_the_download(prefix):
    from dash import no_update

    page, _stored = _finished(prefix)
    broken = {"version": 1, "parts": [{"shape": "nope"}]}
    assert page.save_manifest(1, broken) is no_update
    assert page.save_glb(1, broken) is no_update


@pytest.mark.parametrize("prefix", PAGES)
def test_the_buttons_start_disabled(prefix):
    """There is nothing to save before a build, and an enabled button that
    returns nothing is the shape of a broken page."""
    module, _args = PAGES[prefix]
    # Built from parts: the directory has a hyphen, so it is a namespace
    # package and cannot be turned into a path by replacing dots.
    parts = module.split(".")
    source = REPO / parts[0] / parts[1] / f"{parts[2]}.py"
    text = source.read_text(encoding="utf-8")
    for button in (f"{prefix}-save-json", f"{prefix}-save-glb"):
        block = text.split(f'id="{button}"', 1)[1][:120]
        assert "disabled=True" in block, f"{button} does not start disabled"


# --------------------------------------------------------------------------
# No store, no disk — on every page that can export
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", [
    "docs/generative-3d/sculptor.py",
    "docs/sculpt-from-image/sculpt_from_image.py",
    "docs/scene-manifest/round_trip.py",
])
def test_no_exporting_page_writes_to_disk(path):
    """Bytes in hand, handed to the response. No server-side path, no temp
    file, nothing to clean up — the same reasoning as the viewer's data: URL."""
    source = (REPO / path).read_text(encoding="utf-8")
    for forbidden in ("write_bytes", "write_text", "mkdtemp", "NamedTemporary",
                      "os.makedirs", "shutil."):
        assert forbidden not in source, f"{forbidden!r} appears in {path}"


def test_the_round_trip_page_reads_only_its_own_samples():
    """It does read files — the committed samples — and that is the only
    filesystem access any of this has."""
    source = (REPO / "docs/scene-manifest/round_trip.py").read_text(encoding="utf-8")
    assert "read_text" in source, "the samples are read from disk"
    assert "write" not in source.replace("written", ""), "nothing is written"
