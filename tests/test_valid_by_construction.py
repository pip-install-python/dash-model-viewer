"""A stored manifest must be renderable. It was not, and that took out a page.

THE DEFECT. `lib/sculptor` CLAMPED every field while building — emissive to
0-1, roughness to 0.05-1.0, size and position to their bounds — and
`manifest.from_scene` stored the model's RAW values. `lib/manifest` then
REFUSES what the builder clamps. So a sculpture containing a flame at
`emissive_strength: 3.0` (a value the prompt's own worked example used) drew
perfectly and produced a manifest every consumer of the store rejected.

ONE SWALLOWED `ManifestError` PRODUCED THREE SYMPTOMS, none of which named it:
the texture switch fell back to the untextured render under a note reading
"Draped on screen only"; the .glb button did nothing; the manifest button did
nothing. The owner reported all three separately over two sessions.

So the property is not "the clamps are right". It is that THE BUILD PATH AND
THE STRICT IMPORTER CANNOT DISAGREE — asserted here by rendering both and
comparing bytes.
"""

from __future__ import annotations

import importlib
import json
import pathlib

import pytest

from lib import manifest, sculptor

REPO = pathlib.Path(__file__).resolve().parent.parent

#: Values a model can and does emit that the builder used to accept while the
#: importer refused them. Each is a real shape, not a fuzz case: the flame and
#: the polished lighter are from the owner's own sculpture.
MODEL_SHAPED = {
    "a flame's emissive strength": {"emissive_strength": 3.0},
    "a polished lighter": {"roughness": 0.02},
    "a colour written without its hash": {"color": "B08D57"},
    "an oversized part": {"size": {"x": 40.0, "y": 0.2, "z": 0.2}},
    "a part beyond the scene radius": {"position": {"x": 9.0, "y": 0, "z": 0}},
    "a rotation past a full turn": {"rotation": {"x": 900.0, "y": 0, "z": 0}},
    "a negative metallic": {"metallic": -1.0},
    "a missing name": {"name": None},
    "a zero-size part": {"size": {"x": 0.0, "y": 0.0, "z": 0.0}},
}


def _part(**kw):
    base = {
        "name": "p", "shape": "cone",
        "size": {"x": 0.2, "y": 0.4, "z": 0.2},
        "position": {"x": 0.0, "y": 0.5, "z": 0.0},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
        "color": "#FFB347", "metallic": 0.0,
        "roughness": 0.4, "emissive_strength": 0.0,
    }
    base.update(kw)
    return base


def _scene(*parts):
    return {"name": "Figure", "notes": "a study", "parts": list(parts)}


# --------------------------------------------------------------------------
# The property
# --------------------------------------------------------------------------


@pytest.mark.parametrize("label,override", sorted(MODEL_SHAPED.items()))
def test_what_the_builder_draws_is_what_the_store_keeps(label, override):
    """THE GATE. If these two ever disagree again, the page breaks silently."""
    scene = _scene(_part(**override))
    drawn = sculptor.build(scene)[0]

    stored = manifest.from_scene(scene, {"model": "m", "prompt": "p",
                                         "usd": 0.01, "generated": "2026-09-20"})
    manifest.validate(stored)                      # must not raise
    assert manifest.render(stored)[0] == drawn, (
        f"{label}: the stored manifest renders something else than was drawn"
    )


def test_the_owners_sculpture_shape_end_to_end():
    """The exact case: a lighter at roughness 0.02 beside a flame at emissive
    3.0. The first refusal used to mask the second, so both are here."""
    scene = _scene(
        _part(name="lighter", shape="box", roughness=0.02, metallic=0.9,
              color="B08D57"),
        _part(name="flame", emissive_strength=3.0),
    )
    stored = manifest.from_scene(scene, {"model": "claude-opus-5", "prompt": "x",
                                         "usd": 0.04, "generated": "2026-09-20"})
    assert manifest.validate(stored) is not None
    assert manifest.render(stored)[0] == sculptor.build(scene)[0]
    assert stored["parts"][0]["roughness"] == 0.05
    assert stored["parts"][0]["color"] == "#B08D57"
    assert stored["parts"][1]["emissive_strength"] == 1.0


def test_an_over_long_scene_stores_what_it_drew():
    over = _scene(*[_part(name=f"p{i}") for i in range(sculptor.MAX_PARTS + 4)])
    stored = manifest.from_scene(over)
    assert len(stored["parts"]) == sculptor.MAX_PARTS
    assert manifest.render(stored)[0] == sculptor.build(over)[0]


def test_an_unknown_shape_is_dropped_by_both():
    scene = _scene(_part(), {"shape": "dodecahedron", "name": "nope"}, _part())
    stored = manifest.from_scene(scene)
    assert len(stored["parts"]) == 2
    assert manifest.render(stored)[0] == sculptor.build(scene)[0]


def test_the_clamps_live_in_exactly_one_place():
    """The defect was two copies of the bounds, not a wrong bound. The builder
    must read its numbers from the normaliser rather than clamping again."""
    source = (REPO / "lib" / "sculptor.py").read_text(encoding="utf-8")
    body = source.split("def build_placements", 1)[1].split("def measure", 1)[0]
    assert "normalise_part(" in body, "the builder does not use the normaliser"
    assert "_clamp(" not in body, (
        "build_placements still clamps on its own — that is the second copy "
        "that caused this"
    )


# --------------------------------------------------------------------------
# Nothing is swallowed
# --------------------------------------------------------------------------


def _si():
    return importlib.import_module("docs.sculpt-from-image.sculpt_from_image")


def _bad_store():
    """What the store used to hold: renderable by the builder, refused by the
    importer."""
    return {"version": 1, "name": "Figure",
            "parts": [_part(name="flame", emissive_strength=3.0)]}


def test_a_refused_render_says_so_instead_of_claiming_a_drape():
    """THE DISHONEST STATE. The note read "Draped on screen only" while the
    viewer still showed the untextured build."""
    page = _si()
    src, note, _label = page.retexture("preview", _bad_store(), None)
    assert src is not None                     # no_update: the viewer is left alone
    assert "Draped" not in note
    assert "emissive_strength" in note, "the note must name the field"
    assert "0.0 to 1.0" in note, "and the bound it broke"


@pytest.mark.parametrize("which", ["save_manifest", "save_glb"])
def test_a_refused_download_says_so_instead_of_doing_nothing(which):
    page = _si()
    args = (1, _bad_store()) + (("off", None) if which == "save_glb" else ())
    payload, message, hidden = getattr(page, which)(*args)
    assert payload is not None                 # no_update: no file
    assert "emissive_strength" in message
    assert hidden is False, "the message has to be visible to be a message"


def test_the_healthy_path_still_says_nothing_extra():
    """A message on every successful save would be noise, and noise is how a
    real one gets missed."""
    page = _si()
    good = manifest.from_scene(_scene(_part(name="flame", emissive_strength=3.0)))
    payload, message, hidden = page.save_glb(1, good, "off", None)
    assert isinstance(payload, dict) and payload["filename"].endswith(".glb")
    assert message is hidden  # both no_update


def test_a_generated_manifest_now_survives_the_whole_page():
    """The owner's journey, without a model: build, store, preview, download."""
    page = _si()
    scene = _scene(_part(name="lighter", shape="box", roughness=0.02),
                   _part(name="flame", emissive_strength=3.0))
    stored = manifest.from_scene(scene, {"model": "m", "prompt": "p",
                                         "usd": 0.01, "generated": "2026-09-20"})
    src, note, label = page.retexture("off", stored, None)
    assert isinstance(src, str) and src.startswith("data:model/gltf-binary")
    assert "Could not render" not in note
    assert label == "Download .glb"

    payload, _m, _h = page.save_glb(1, stored, "off", None)
    assert payload["filename"].endswith(".glb")
    payload, _m, _h = page.save_manifest(1, stored)
    assert json.loads(payload["content"])["version"] == 1
