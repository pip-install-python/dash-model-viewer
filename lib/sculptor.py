"""Text → a real `.glb`, with Claude as a scene compiler.

THE IDEA
--------
Asking a language model for a mesh gets you plausible nonsense: vertex lists it
cannot see, winding orders it cannot check, normals it cannot verify. Asking it
"what shape is a lighthouse" gets you *a tall white cylinder, a red cone on top,
a small glowing sphere inside, a dark ring around the gallery* — which is a
thing code can build exactly.

So the model never emits geometry. It emits a **parts list**: primitives with
sizes, positions, rotations and PBR materials. `lib.glb` turns that into a real
glTF. Every triangle is deterministic Python; the model supplies only judgement.

That split is what makes this cheap, inspectable, reproducible, and free of any
third-party 3D service — and it is why the output renders, orbits and works in
AR rather than being a picture of a 3D object.

DELIVERY
--------
The result is handed to `ModelViewer` as a `data:` URL. There is no upload
store, no temp directory and no cleanup job — which also means there is no
anonymous write surface to cap or expire on a public host. The ceiling is the
practical size of a data URL, so the part budget is small on purpose.
"""

from __future__ import annotations

import base64
import json
import os
import time
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from lib import build_stream, glb, openai_client, spend, texture

MODEL = "claude-opus-5"
MAX_TOKENS = 4000
EFFORT = "medium"

#: The vocabulary. Everything the model may build with, and nothing else.
SHAPES = ("box", "sphere", "cylinder", "cone", "torus", "plane")

#: What each `size` component MEANS, per shape — the single source for both the
#: prompt the model reads and the table on /scene-manifest. `None` means the
#: builder ignores that component.
#:
#: THIS TABLE EXISTS BECAUSE THE PROMPT AND THE CODE DISAGREED. The prompt said
#: "size = radius" for sphere, cylinder, cone and torus while the dispatch
#: passes `size.x / 2` to the builders — so every curved part a model produced
#: was HALF the size it intended, while every box and plane was exact. The
#: silhouette was right and only the curved masses were wrong, which is
#: invisible to read and very hard to attribute.
#:
#: A prompt is documentation that a model reads. It is pinned to the enforcing
#: code for the same reason the page is.
SIZE_SEMANTICS = {
    "box": ("width", "height", "depth"),
    "sphere": ("diameter", None, None),
    "cylinder": ("diameter", "height", None),
    "cone": ("base diameter", "height", None),
    "torus": ("ring diameter", None, "tube diameter"),
    "plane": ("width", None, "depth"),
}

#: Shapes whose `size.x` the dispatch halves. For these the prompt must never
#: say "radius"; `tests/test_components.py` has no opinion on prompts, so
#: `tests/test_prompt_matches_the_code.py` holds this.
HALVED_SHAPES = ("sphere", "cylinder", "cone", "torus")


def size_semantics_rows():
    """`[(shape, "size.x = …, size.y = …"), …]` — rendered into the prompt."""
    rows = []
    for shape in SHAPES:
        parts = [
            f"size.{axis} = {meaning}"
            for axis, meaning in zip("xyz", SIZE_SEMANTICS[shape])
            if meaning
        ]
        rows.append((shape, ", ".join(parts)))
    return rows


def _vocabulary_block():
    width = max(len(s) for s in SHAPES)
    return "\n".join(
        f"  {shape:<{width}}  {meaning}"
        for shape, meaning in size_semantics_rows()
    )


#: Hard ceilings. A model asked for "a city" will happily emit 400 parts; at
#: ~1.5 KB of geometry each that is a data URL no browser will accept.
MAX_PARTS = 28
MAX_EXTENT = 4.0          # metres, any single dimension
MAX_SCENE_RADIUS = 5.0    # metres from origin
MAX_GLB_BYTES = 3_000_000

# --- manifest v2 bounds -----------------------------------------------------
# Declared here, beside MAX_PARTS, so the schema page's v2 rows READ them
# rather than restating them. The v1 rows already work that way and the habit
# is why four wrong lines were caught in that page's draft.
#
# Inert until v2 lands: nothing imports these yet. They are here first so the
# page and the validator cannot be written against different numbers.

#: How deep a `group` may nest before the expander refuses. Four levels is a
#: cart (scene -> cart -> wheel-assembly -> leaf) with one to spare; deeper is
#: almost always a model repeating itself rather than describing structure.
MAX_DEPTH = 4

#: How many entries `defs` may hold. A sculpture with more than eight distinct
#: repeated sub-assemblies is not using instancing, it is using a parts bin.
MAX_DEFS = 8

#: The prompt versions /benchmark can sweep.
#:
#: v1 IS THE DEFAULT EVERYWHERE A SCULPTURE IS GENERATED, and stays that way
#: until there is a measurement. SYSTEM_V2 is better by ARGUMENT — it teaches
#: defs/ref/group, and it tells a model that parts may interpenetrate where
#: they join — but the entire claim is "it produces better sculptures", and
#: only model runs can show that. Making it the default on an argument would
#: be exactly the move this repo keeps catching itself making. Until a sweep
#: exists, the only place v2 runs is /benchmark, where running it IS the point.
PROMPT_VERSIONS = ("v1", "v2")
DEFAULT_PROMPT_VERSION = "v1"

#: What each version is for, shown on the page beside the checkbox.
PROMPT_VERSION_LABELS = {
    "v1": "v1 (shipped)",
    "v2": "v2 (defs + joints)",
}


#: `MAX_PARTS` counts LEAF parts AFTER expansion in v2 — a `ref` costs its
#: def's leaf count every time it is placed. Stated here because the number is
#: unchanged and its meaning is not.

_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


@dataclass
class SculptResult:
    ok: bool
    reason: str = ""
    glb: bytes = b""
    data_url: str = ""
    manifest: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    part_count: int = 0
    # Everything below exists for the benchmark page: you cannot compare two
    # settings without knowing what each one cost and produced.
    model: str = ""
    effort: str = ""
    max_tokens: int = 0
    seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    usd: float = 0.0
    stop_reason: str = ""
    triangles: int = 0
    palette: int = 0
    #: Which system prompt produced this. Recorded so a benchmark row can say
    #: what it was comparing rather than relying on the reader's memory.
    prompt_version: str = DEFAULT_PROMPT_VERSION


def available() -> bool:
    """Anthropic. Kept as-is: /generative-3d and /benchmark both call it."""
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def provider_of(model: str) -> str:
    """Which API a model id belongs to.

    Decided by the PRICING tables rather than by prefix-matching the id, so a
    model this build cannot meter is never routed anywhere — it falls through
    to a plain "unknown model" instead of being sent to a provider on the
    strength of its name.
    """
    if model in openai_client.PRICING:
        return "openai"
    return "anthropic"


def available_for(model: str) -> bool:
    return openai_client.available() if provider_of(model) == "openai" else available()


# --------------------------------------------------------------------------
# Prompt
# --------------------------------------------------------------------------

SYSTEM = f"""You compose 3D sculptures out of primitive shapes, for display in
Google's <model-viewer>. You are a scene compiler, not a modeller: you choose
shapes, places and materials, and code builds the geometry exactly.

THE VOCABULARY — you may use nothing else:
{_vocabulary_block()}

SIZE IS ALWAYS A FULL WIDTH, NEVER A RADIUS. A sphere with size.x = 0.4 is
0.4m across, not 0.8m. A torus is size.x + size.z wide overall, because the
tube stands out on both sides of the ring.

COORDINATES: right-handed, +Y is UP, -Z is away from the viewer.
The sculpture stands ON the ground plane y=0. Nothing may sit below y=0 unless
it is deliberately sunken. Build UPWARD from there.

SIZE AND PLACE:
- Every dimension in metres. No single dimension over {MAX_EXTENT}m, nothing
  further than {MAX_SCENE_RADIUS}m from the origin.
- Aim for something a person could stand next to: roughly 0.5m to 2.5m tall.
- position is the CENTRE of the part. A cylinder of height 1.4 resting on the
  ground therefore has position.y = 0.7, not 0.

COMPOSITION — this is the part that decides whether it reads as art:
- Between 5 and {MAX_PARTS} parts. Fewer than 5 reads as a diagram; more than
  ~25 reads as noise at a glance.
- Vary scale deliberately: a few large masses that carry the silhouette, then
  smaller parts for detail. Repetition with variation reads better than
  symmetry everywhere.
- Rotation is free and underused — tilt, lean and offset parts rather than
  stacking everything axis-aligned.

MATERIAL — <model-viewer> renders real PBR, so use it:
- metallic near 1.0 with roughness under 0.3 gives polished metal; metallic 0
  with roughness 0.8 gives matte plaster or stone.
- emissive_strength above 0 makes a part GLOW. Used on one or two small parts
  it carries a whole piece; used everywhere it flattens it.
- Pick a deliberate palette of three or four colours and reuse them. A
  different colour per part looks like a test scene, not a sculpture.

Return the parts list. Keep `notes` to one sentence about the idea."""


#: The v2 prompt. INERT — nothing imports it yet; it exists so the before/after
#: measurement has both halves committed and reviewable before either runs.
#:
#: Rewritten ONCE in the v2 vocabulary, per the kickoff: the measurement is the
#: acceptance, not the length. Its vocabulary block renders from SIZE_SEMANTICS
#: like v1's, so the radius/diameter class of error cannot reappear here.
#:
#: G3 will add `extrude` and `lathe` to the shape list. That is an addition to
#: the rendered block, not another rewrite.
SYSTEM_V2 = f"""You compose 3D sculptures for display in Google's
<model-viewer>. You are a scene compiler, not a modeller: you choose shapes,
places and materials, and code builds the geometry exactly.

PRIMITIVES — you may use nothing else:
{_vocabulary_block()}

SIZE IS ALWAYS A FULL WIDTH, NEVER A RADIUS. A sphere with size.x = 0.4 is
0.4m across, not 0.8m. A torus is size.x + size.z wide overall, because the
tube stands out on both sides of the ring.

COORDINATES: right-handed, +Y is UP, -Z is away from the viewer. The sculpture
stands ON the ground plane y=0. `position` is the CENTRE of a part: a cylinder
of height 1.4 resting on the ground has position.y = 0.7, not 0.

STRUCTURE — this is what is new, and it is what makes a good sculpture cheap.

A part may be a GROUP: {{"shape": "group", "children": [...]}} with its own
position and rotation and NO size and NO material. Its children are positioned
in the group's OWN coordinates, so you place the assembly once and its parts
stay together. Rotate the group and everything in it rotates.

A part may be a REFERENCE: {{"ref": "wheel", "position": ..., "rotation": ...}}
— one placement of something defined once in `defs`. Define a wheel in `defs`,
place it four times, and you have written it once. A reference cannot change
the colour or size of what it places; that is what lets four placements share
one piece of geometry.

USE THEM. Anything that appears more than once — a wheel, a column, a window,
a leg, a baluster — belongs in `defs` and is placed by reference. A sculpture
that writes the same wheel out four times is spending its part budget on
repetition instead of on detail.

THE BUDGET, which groups change the arithmetic of:
- At most {MAX_PARTS} LEAF parts after every reference is expanded. A wheel of
  3 leaves placed 4 times costs 12, not 4 and not 1.
- At most {MAX_DEFS} entries in `defs`.
- Groups nest at most {MAX_DEPTH} deep.
- No single dimension over {MAX_EXTENT}m; nothing further than
  {MAX_SCENE_RADIUS}m from the origin.

A WORKED EXAMPLE — a hand cart. One wheel, defined once, placed four times:

  "defs": {{
    "wheel": {{
      "name": "wheel", "shape": "group",
      "position": {{"x": 0, "y": 0, "z": 0}},
      "rotation": {{"x": 0, "y": 0, "z": 0}},
      "children": [
        {{"name": "tyre", "shape": "torus",
          "size": {{"x": 0.44, "y": 0.1, "z": 0.08}},
          "position": {{"x": 0, "y": 0, "z": 0}},
          "rotation": {{"x": 0, "y": 90, "z": 0}},
          "color": "#2E2A28", "metallic": 0.0,
          "roughness": 0.9, "emissive_strength": 0.0}},
        {{"name": "hub", "shape": "cylinder",
          "size": {{"x": 0.1, "y": 0.09, "z": 0.1}},
          "position": {{"x": 0, "y": 0, "z": 0}},
          "rotation": {{"x": 0, "y": 0, "z": 90}},
          "color": "#8A6A3C", "metallic": 0.2,
          "roughness": 0.6, "emissive_strength": 0.0}}
      ]
    }}
  }},
  "parts": [
    {{"name": "bed", "shape": "box",
      "size": {{"x": 1.3, "y": 0.12, "z": 0.7}},
      "position": {{"x": 0, "y": 0.46, "z": 0}},
      "rotation": {{"x": 0, "y": 0, "z": 0}},
      "color": "#8A6A3C", "metallic": 0.1,
      "roughness": 0.7, "emissive_strength": 0.0}},
    {{"name": "front left wheel", "ref": "wheel",
      "position": {{"x": -0.5, "y": 0.26, "z": 0.38}},
      "rotation": {{"x": 0, "y": 0, "z": 0}}}},
    {{"name": "front right wheel", "ref": "wheel",
      "position": {{"x": -0.5, "y": 0.26, "z": -0.38}},
      "rotation": {{"x": 0, "y": 0, "z": 0}}}},
    {{"name": "rear left wheel", "ref": "wheel",
      "position": {{"x": 0.5, "y": 0.26, "z": 0.38}},
      "rotation": {{"x": 0, "y": 0, "z": 0}}}},
    {{"name": "rear right wheel", "ref": "wheel",
      "position": {{"x": 0.5, "y": 0.26, "z": -0.38}},
      "rotation": {{"x": 0, "y": 0, "z": 0}}}}
  ]

That is nine LEAF parts after expansion — eight wheel parts plus the bed — but
only seven entries written: the wheel's two children once, four placements, and
the bed. Referencing does not reduce the leaf budget; it reduces what you have
to get right, and it guarantees the four wheels are identical because they ARE
the same wheel. Spend the parts you save on detail, not on repetition.

JOINTS — parts MAY AND SHOULD INTERPENETRATE where they join. A lamp sits
INTO the top of its tower, not balanced on it; a column is sunk INTO the floor,
not resting on it; an arm goes INTO the body. Overlap by a few centimetres
wherever two parts meet.
This matters more than it sounds. Parts that merely touch — or that leave a
millimetre of air — read as separate objects stacked in a pile, however well
placed. Parts that interpenetrate read as one carved mass. Do not make surfaces
meet exactly; push them through each other.

COMPOSITION — what decides whether it reads as art rather than as a diagram:
- Vary scale deliberately: a few large masses carry the silhouette, then
  smaller parts for detail. Repetition WITH variation reads better than
  symmetry everywhere — vary the placement, not the piece.
- Rotation is free and underused. Tilt, lean and offset rather than stacking
  everything axis-aligned.
- metallic near 1.0 with roughness under 0.3 is polished metal; metallic 0 with
  roughness 0.8 is matte plaster or stone.
- emissive_strength above 0 makes a part GLOW, and 1.0 is the ceiling. On one
  or two small parts it carries a whole piece; everywhere it flattens it.
- Pick a deliberate palette of three or four colours and reuse them. A
  different colour per part looks like a test scene, not a sculpture.

Keep `notes` to one sentence about the idea."""


def system_for(prompt_version: str) -> str:
    """The system prompt for a version name.

    An unknown name falls back to the default rather than raising: this is
    reached from a sweep, and a stale value in a control should run the
    shipped prompt rather than take the page down.
    """
    return SYSTEM_V2 if prompt_version == "v2" else SYSTEM


def _schema() -> Dict[str, Any]:
    # NOTE: structured outputs require every object to be closed
    # (additionalProperties: false), so no free-form maps anywhere.
    vec = {
        "type": "object",
        "properties": {
            "x": {"type": "number"},
            "y": {"type": "number"},
            "z": {"type": "number"},
        },
        "required": ["x", "y", "z"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "notes": {"type": "string"},
            "parts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "shape": {"type": "string", "enum": list(SHAPES)},
                        "size": vec,
                        "position": vec,
                        "rotation": vec,
                        "color": {
                            "type": "string",
                            "description": "hex, e.g. #C8A24B",
                        },
                        "metallic": {"type": "number"},
                        "roughness": {"type": "number"},
                        "emissive_strength": {"type": "number"},
                    },
                    "required": [
                        "name", "shape", "size", "position", "rotation",
                        "color", "metallic", "roughness", "emissive_strength",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["name", "notes", "parts"],
        "additionalProperties": False,
    }


# --------------------------------------------------------------------------
# Validation — shape is not sanity
# --------------------------------------------------------------------------


def _colour(value: str) -> Tuple[float, float, float]:
    match = _HEX.match((value or "").strip())
    if not match:
        return (0.75, 0.75, 0.78)
    hexstr = match.group(1)
    srgb = [int(hexstr[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    # glTF baseColorFactor is LINEAR, not sRGB. Skipping this makes every
    # generated palette render noticeably washed out.
    return tuple(
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb
    )


#: What an unreadable colour becomes. Chosen so `_colour()` maps it to very
#: nearly the linear fallback the builder already used, so normalising a part
#: does not change how it is drawn.
DEFAULT_COLOR = "#E1E1E5"


def normalise_part(part: Any, index: int = 0) -> Optional[Dict[str, Any]]:
    """A model's raw part -> one that is VALID BY CONSTRUCTION.

    THE BUG THIS EXISTS FOR. The builder CLAMPED (`emissive_strength` to 0-1,
    `roughness` to 0.05-1.0, and so on) while `manifest.from_scene` stored the
    model's RAW values, and the importer REFUSES what the builder clamps. So a
    sculpture containing a flame at `emissive_strength: 3.0` — which the
    prompt's own worked example once used — rendered perfectly and produced a
    manifest that every consumer of the store rejected. One swallowed
    `ManifestError` then took out the texture switch and both downloads at
    once, under a note that claimed the image had been draped.

    Returns None when the shape is unknown, which is the one case the builder
    drops rather than corrects.

    THIS IS THE ONLY PLACE THE CLAMPS LIVE. The builder reads its numbers from
    here and `from_scene` stores exactly these, so the two cannot disagree
    again — which was the actual defect, not any individual bound.
    """
    if not isinstance(part, dict):
        return None
    shape = str(part.get("shape", "")).lower()
    if shape not in SHAPES:
        return None

    size = part.get("size") or {}
    pos = part.get("position") or {}
    rot = part.get("rotation") or {}
    match = _HEX.match(str(part.get("color") or "").strip())
    return {
        "name": str(part.get("name") or f"part{index}")[:48],
        "shape": shape,
        "size": {axis: _clamp(size.get(axis), 0.01, MAX_EXTENT, 0.5)
                 for axis in ("x", "y", "z")},
        "position": {axis: _clamp(pos.get(axis), -MAX_SCENE_RADIUS,
                                  MAX_SCENE_RADIUS, 0.0)
                     for axis in ("x", "y", "z")},
        "rotation": {axis: _clamp(rot.get(axis), -360.0, 360.0, 0.0)
                     for axis in ("x", "y", "z")},
        # The '#' is added here because the builder accepted a bare "E8E4DC"
        # and the importer refused it — the same class of divergence.
        "color": f"#{match.group(1).upper()}" if match else DEFAULT_COLOR,
        "metallic": _clamp(part.get("metallic"), 0.0, 1.0, 0.0),
        "roughness": _clamp(part.get("roughness"), 0.05, 1.0, 0.8),
        "emissive_strength": _clamp(part.get("emissive_strength"), 0.0, 1.0, 0.0),
    }


def normalise_scene(scene: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Every part of a scene, normalised. Returns (parts, notes).

    Truncates BEFORE dropping unknown shapes, which is the order `build()`
    has always used — so the two select the same parts from an over-long
    scene, not merely the same number of them.
    """
    raw = list(scene.get("parts") or [])
    notes: List[str] = []
    if len(raw) > MAX_PARTS:
        notes.append(f"kept the first {MAX_PARTS} of {len(raw)} parts")
        raw = raw[:MAX_PARTS]
    parts: List[Dict[str, Any]] = []
    for index, part in enumerate(raw):
        clean = normalise_part(part, index)
        if clean is None:
            shape = str((part or {}).get("shape", "")).lower() if isinstance(part, dict) else ""
            notes.append(f"dropped part {index} — unknown shape {shape!r}")
            continue
        parts.append(clean)
    return parts, notes


def _clamp(value: Any, low: float, high: float, default: float) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return default


def build(scene: Dict[str, Any],
          texture_png: Optional[bytes] = None) -> Tuple[bytes, List[str], int]:
    """Turn a validated parts list into glb bytes. Pure, and unit-testable."""
    notes: List[str] = []
    parts = scene.get("parts") or []

    if len(parts) > MAX_PARTS:
        notes.append(f"kept the first {MAX_PARTS} of {len(parts)} parts")
        parts = parts[:MAX_PARTS]

    return build_placements(
        [
            {
                "style": part,
                "position": (
                    _clamp((part.get("position") or {}).get("x"),
                           -MAX_SCENE_RADIUS, MAX_SCENE_RADIUS, 0.0),
                    _clamp((part.get("position") or {}).get("y"),
                           -MAX_SCENE_RADIUS, MAX_SCENE_RADIUS, 0.0),
                    _clamp((part.get("position") or {}).get("z"),
                           -MAX_SCENE_RADIUS, MAX_SCENE_RADIUS, 0.0),
                ),
                "quat": glb._euler_to_quat(
                    _clamp((part.get("rotation") or {}).get("x"), -360, 360, 0.0),
                    _clamp((part.get("rotation") or {}).get("y"), -360, 360, 0.0),
                    _clamp((part.get("rotation") or {}).get("z"), -360, 360, 0.0),
                ),
                "share": None,
                "name": part.get("name") or f"part{i}",
            }
            for i, part in enumerate(parts)
        ],
        texture_png=texture_png,
        notes=notes,
    )


def build_placements(placements: List[Dict[str, Any]],
                     texture_png: Optional[bytes] = None,
                     notes: Optional[List[str]] = None
                     ) -> Tuple[bytes, List[str], int]:
    """Draw already-placed leaves. The one implementation both paths reach.

    `build()` hands it a flat scene straight from a model, where the values are
    untrusted and get clamped on the way in; `manifest.expand()` hands it the
    leaves of a nested manifest, already validated and with every transform
    composed. Keeping ONE builder is what makes "a nested manifest and the
    same sculpture written flat put every node in the same place" a fact about
    the code rather than a coincidence between two copies of it.

    A `share` key means "this came from a def": all placements carrying the
    same key get ONE material and ONE mesh, which is where instancing pays.
    """
    notes = notes if notes is not None else []
    if len(placements) > MAX_PARTS:
        notes.append(f"kept the first {MAX_PARTS} of {len(placements)} parts")
        placements = placements[:MAX_PARTS]

    builder = glb.GLBBuilder()
    built: List[glb.Mesh] = []
    shared_materials: Dict[str, glb.Material] = {}
    used = 0
    for i, placement in enumerate(placements):
        # NORMALISED HERE, and nowhere else. `manifest.from_scene` stores the
        # output of this same function, so what is drawn and what is stored
        # cannot drift apart — see normalise_part.
        part = normalise_part(placement["style"], i)
        if part is None:
            raw = placement["style"] if isinstance(placement["style"], dict) else {}
            notes.append(
                f"dropped part {i} — unknown shape "
                f"{str(raw.get('shape', '')).lower()!r}"
            )
            continue

        shape = part["shape"]
        w, h, d = part["size"]["x"], part["size"]["y"], part["size"]["z"]

        share = placement.get("share")
        name = str(placement.get("name") or part["name"])[:48]
        if share is not None and share in shared_materials:
            material = shared_materials[share]
        else:
            colour = _colour(part["color"])
            material = glb.Material(
                base_color=colour,
                metallic=part["metallic"],
                roughness=part["roughness"],
                emissive=tuple(c * part["emissive_strength"] for c in colour),
                name=name,
            )
            if share is not None:
                shared_materials[share] = material

        kw = dict(
            material=material,
            translation=tuple(placement["position"]),
            rotation_quat=placement["quat"],
            name=name,
            share_key=share,
        )

        if shape == "box":
            mesh = glb.box(w, h, d, **kw)
        elif shape == "sphere":
            mesh = glb.sphere(w / 2, **kw)
        elif shape == "cylinder":
            mesh = glb.cylinder(w / 2, h, **kw)
        elif shape == "cone":
            mesh = glb.cone(w / 2, h, **kw)
        elif shape == "torus":
            mesh = glb.torus(w / 2, max(0.005, d / 2), **kw)
        else:  # plane
            mesh = glb.plane(w, d, **kw)

        built.append(mesh)
        used += 1

    if not used:
        raise ValueError("no usable parts in the scene")

    # Draped AFTER placement, over the finished geometry, so one image
    # covers the whole model once instead of repeating per primitive. It
    # reads world positions, so it is indifferent to how the parts were
    # built — see lib/texture.py.
    if texture_png:
        texture.drape(built, texture_png)
        notes.append("draped the uploaded image across the sculpture")
    builder.extend(built)

    data = builder.build()
    if len(data) > MAX_GLB_BYTES:
        raise ValueError(
            f"the sculpture came to {len(data):,} bytes, over the "
            f"{MAX_GLB_BYTES:,} data-URL ceiling"
        )
    return data, notes, used


def measure(scene: Dict[str, Any], data: bytes) -> Tuple[int, int]:
    """(triangles, distinct colours) for a built scene.

    Palette size is the interesting one. The single highest-return line in the
    system prompt is "pick three or four colours and reuse them", so counting
    distinct base colours measures whether a given setting actually followed
    it — which is a far better quality proxy for this domain than part count.
    """
    import json as _json
    import struct as _struct

    length = _struct.unpack("<I", data[12:16])[0]
    gltf = _json.loads(data[20:20 + length])
    triangles = 0
    for mesh in gltf.get("meshes", []):
        for prim in mesh.get("primitives", []):
            triangles += gltf["accessors"][prim["indices"]]["count"] // 3
    palette = {
        tuple(round(c, 4) for c in m["pbrMetallicRoughness"]["baseColorFactor"][:3])
        for m in gltf.get("materials", [])
    }
    return triangles, len(palette)


def to_data_url(data: bytes) -> str:
    """`<model-viewer>` accepts a data: URL as `src`, so nothing is stored."""
    return "data:model/gltf-binary;base64," + base64.b64encode(data).decode("ascii")


# --------------------------------------------------------------------------
# The call
# --------------------------------------------------------------------------


def sculpt(
    request: str,
    style: Optional[str] = None,
    model: str = MODEL,
    effort: str = EFFORT,
    max_tokens: int = MAX_TOKENS,
    enforce_budget: bool = True,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
) -> SculptResult:
    """One sculpt. The knobs are arguments so /benchmark can sweep them."""
    request = (request or "").strip()
    meta = dict(model=model, effort=effort, max_tokens=max_tokens,
                prompt_version=prompt_version)
    if not request:
        return SculptResult(ok=False, reason="Describe what you want sculpted.", **meta)
    if len(request) > 400:
        return SculptResult(ok=False, reason="Keep the request under 400 characters.", **meta)
    if enforce_budget:
        verdict = spend.check(1, spend.estimate_usd(model, max_tokens))
        if not verdict.allowed:
            return SculptResult(ok=False, reason=verdict.reason, **meta)
    if provider_of(model) == "openai":
        return _sculpt_openai(prompt_for(request, style), model, max_tokens, meta,
                              system=system_for(prompt_version))

    if not available():
        return SculptResult(
            ok=False,
            reason=(
                "ANTHROPIC_API_KEY is not set on this host, so the sculptor is "
                "off. The schema, the clamping and the glTF writer are in "
                "lib/sculptor.py and lib/glb.py and need no key to read."
            ),
            **meta,
        )

    try:
        import anthropic
    except ImportError:
        return SculptResult(ok=False, reason="The `anthropic` package is not installed.", **meta)

    prompt = prompt_for(request, style)
    output_config: Dict[str, Any] = {
        "format": {"type": "json_schema", "schema": _schema()}
    }
    # Only send `effort` to a model that accepts it — otherwise the request is
    # rejected, and a benchmark that varies a parameter the model ignores would
    # present N identical runs as a comparison.
    if effort and model in spend.EFFORT_CAPABLE:
        output_config["effort"] = effort

    client = anthropic.Anthropic()
    started = time.perf_counter()
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_for(prompt_version),
            output_config=output_config,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # noqa: BLE001
        return SculptResult(ok=False, reason=f"{type(exc).__name__}: {exc}", **meta)
    elapsed = time.perf_counter() - started

    usage = getattr(response, "usage", None)
    in_tok = int(getattr(usage, "input_tokens", 0) or 0)
    out_tok = int(getattr(usage, "output_tokens", 0) or 0)
    usd = spend.record(model, in_tok, out_tok)
    measured = dict(
        seconds=elapsed, input_tokens=in_tok, output_tokens=out_tok, usd=usd,
        stop_reason=str(response.stop_reason or ""), **meta,
    )

    if response.stop_reason == "refusal":
        return SculptResult(
            ok=False, reason="The request was declined by the safety system.", **measured)

    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        scene = json.loads(text)
    except ValueError:
        # `max_tokens` is the usual cause: on Opus 5 it bounds thinking AND
        # response text together, so a low budget truncates the JSON mid-object.
        hint = (" The output hit max_tokens, so the JSON was cut off — that is "
                "the budget, not the model.") if response.stop_reason == "max_tokens" else ""
        return SculptResult(
            ok=False, reason="The model did not return usable JSON." + hint, **measured)

    return _finish(scene, measured)


def prompt_for(request: str, style: Optional[str]) -> str:
    return request if not style else f"{request}\n\nStyle: {style}"


#: Appended to SYSTEM when an image is the subject.
#:
#: The first line is the one that matters, and it is a promise the page repeats
#: in prose: this is INTERPRETATION, not reconstruction. Nothing here measures
#: the photograph — there is no depth estimation, no photogrammetry and no
#: mesh fitting. The model looks at a picture and composes a sculpture that
#: evokes it out of the same six primitives everything else on this site uses.
#: A user who uploads a photo of their car and gets something car-shaped but
#: not THEIR car has been told, up front, exactly that.
IMAGE_SYSTEM = """
YOU ARE LOOKING AT AN IMAGE. Compose a sculpture that EVOKES it — its masses,
its proportions, its palette, its mood. You are not reconstructing it and you
cannot: your vocabulary is six primitives, and the result is a sculpture in the
spirit of the picture rather than a copy of it.

Read the image for:
- the dominant SHAPES and how they stack or lean
- the PROPORTIONS — what is tall, what is wide, what is small
- the PALETTE — sample three or four colours actually present, and reuse them
- one detail worth keeping, rendered as a small part

Do not attempt text, faces, or fine surface detail. They will not survive the
vocabulary and they are what makes an interpretation look like a failed copy.
"""


def sculpt_image(
    image_data_url: str,
    hint: str = "",
    model: str = MODEL,
    effort: str = EFFORT,
    max_tokens: int = MAX_TOKENS,
    enforce_budget: bool = True,
) -> SculptResult:
    """An uploaded image -> a parts list -> a real `.glb`.

    Same schema, same clamps, same glTF writer and the SAME spend gate as the
    text path; the only difference is that the model is shown a picture. The
    image is passed as the data URL the browser produced and is never written
    anywhere.
    """
    meta = dict(model=model, effort=effort, max_tokens=max_tokens)
    if not image_data_url:
        return SculptResult(ok=False, reason="Upload an image first.", **meta)
    if enforce_budget:
        verdict = spend.check(1, spend.estimate_usd(model, max_tokens))
        if not verdict.allowed:
            return SculptResult(ok=False, reason=verdict.reason, **meta)
    if not available_for(model):
        return SculptResult(
            ok=False,
            reason=(
                openai_client.status()
                if provider_of(model) == "openai"
                else "ANTHROPIC_API_KEY is not set on this host, so this page is off."
            ),
            **meta,
        )

    system = SYSTEM + "\n" + IMAGE_SYSTEM
    prompt = hint.strip() or "Compose a sculpture evoking this image."

    if provider_of(model) == "openai":
        started = time.perf_counter()
        try:
            scene, usage, stop_reason = openai_client.complete_json(
                model=model, system=system, prompt=prompt, schema=_schema(),
                max_tokens=max_tokens, image_data_url=image_data_url,
            )
        except Exception as exc:  # noqa: BLE001
            return SculptResult(ok=False, reason=f"{type(exc).__name__}: {exc}", **meta)
        in_tok = usage.get("input_tokens", 0)
        out_tok = usage.get("output_tokens", 0)
        measured = dict(
            seconds=time.perf_counter() - started,
            input_tokens=in_tok, output_tokens=out_tok,
            usd=spend.record(model, in_tok, out_tok),
            stop_reason=stop_reason, **meta,
        )
        if stop_reason == "length":
            return SculptResult(
                ok=False,
                reason="The output hit max_completion_tokens, so the JSON was cut off.",
                **measured,
            )
        return _finish(scene, measured)

    try:
        import anthropic
    except ImportError:
        return SculptResult(ok=False, reason="The `anthropic` package is not installed.", **meta)

    header, _, payload = image_data_url.partition(",")
    media_type = header[5:].split(";")[0] if header.startswith("data:") else "image/png"

    client = anthropic.Anthropic()
    started = time.perf_counter()
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            output_config={"format": {"type": "json_schema", "schema": _schema()}},
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": payload,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
    except Exception as exc:  # noqa: BLE001
        return SculptResult(ok=False, reason=f"{type(exc).__name__}: {exc}", **meta)

    usage = getattr(response, "usage", None)
    in_tok = int(getattr(usage, "input_tokens", 0) or 0)
    out_tok = int(getattr(usage, "output_tokens", 0) or 0)
    measured = dict(
        seconds=time.perf_counter() - started,
        input_tokens=in_tok, output_tokens=out_tok,
        usd=spend.record(model, in_tok, out_tok),
        stop_reason=str(response.stop_reason or ""), **meta,
    )
    if response.stop_reason == "refusal":
        return SculptResult(
            ok=False, reason="The request was declined by the safety system.", **measured)

    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        scene = json.loads(text)
    except ValueError:
        return SculptResult(
            ok=False, reason="The model did not return usable JSON.", **measured)
    return _finish(scene, measured)


def sculpt_image_streaming(
    run_id: str,
    image_data_url: str,
    hint: str = "",
    model: str = MODEL,
    max_tokens: int = MAX_TOKENS,
) -> SculptResult:
    """`sculpt_image`, assembled part by part. Charges once, like the text path."""
    build_stream.emit(run_id, {"phase": "asking", "model": model})
    result = sculpt_image(
        image_data_url, hint=hint, model=model, max_tokens=max_tokens
    )
    return _stream_assembly(run_id, result)


def _sculpt_openai(
    prompt: str, model: str, max_tokens: int, meta: Dict[str, Any],
    system: str = "",
) -> SculptResult:
    """The OpenAI path. Same schema, same clamps, same GLB writer.

    Kept to the same shape as the Anthropic path on purpose: a failure returns
    a SculptResult with a reason rather than raising, because /benchmark sweeps
    settings and one bad combination must not take the sweep down.
    """
    if not openai_client.available():
        return SculptResult(ok=False, reason=openai_client.status(), **meta)

    started = time.perf_counter()
    try:
        scene, usage, stop_reason = openai_client.complete_json(
            model=model,
            system=system or SYSTEM,
            prompt=prompt,
            schema=_schema(),
            max_tokens=max_tokens,
        )
    except Exception as exc:  # noqa: BLE001
        return SculptResult(ok=False, reason=f"{type(exc).__name__}: {exc}", **meta)
    elapsed = time.perf_counter() - started

    in_tok = usage.get("input_tokens", 0)
    out_tok = usage.get("output_tokens", 0)
    measured = dict(
        seconds=elapsed,
        input_tokens=in_tok,
        output_tokens=out_tok,
        # Recorded against the SAME gate as the Anthropic path — one budget for
        # the host, not one per provider.
        usd=spend.record(model, in_tok, out_tok),
        stop_reason=stop_reason,
        **meta,
    )

    if stop_reason == "length":
        return SculptResult(
            ok=False,
            reason=(
                "The output hit max_completion_tokens, so the JSON was cut off "
                "— that is the budget, not the model."
            ),
            **measured,
        )
    if not isinstance(scene, dict) or "parts" not in scene:
        return SculptResult(
            ok=False, reason="The model did not return usable JSON.", **measured
        )
    return _finish(scene, measured)


def sculpt_streaming(
    run_id: str,
    request: str,
    style: Optional[str] = None,
    model: str = MODEL,
    effort: str = EFFORT,
    max_tokens: int = MAX_TOKENS,
) -> SculptResult:
    """One sculpt, emitting progress as it assembles.

    THE SPEND GATE STILL WRAPS THE BUILD ONCE. Streaming adds no model calls:
    the model returns the whole parts list in a single response, and what is
    streamed is the ASSEMBLY of that list into geometry. Emitting per part
    must never be mistaken for charging per part, which is why this delegates
    the single metered call to `sculpt()` rather than re-implementing it.

    The progressive `.glb`s are the point: each one is a real, complete model
    containing the parts so far, so the viewer shows the sculpture appearing
    piece by piece instead of a spinner followed by a finished object.
    """
    build_stream.emit(run_id, {"phase": "asking", "model": model})
    result = sculpt(
        request, style=style, model=model, effort=effort, max_tokens=max_tokens
    )
    return _stream_assembly(run_id, result)


def _stream_assembly(run_id: str, result: SculptResult) -> SculptResult:
    """Emit a finished scene one part at a time.

    Shared by the text and image entry points: the assembly is identical
    whichever produced the parts list, and a second copy would be a second
    place for the events to drift out of step with the page that reads them.
    """
    if not result.ok:
        build_stream.emit(run_id, {"phase": "failed", "reason": result.reason})
        build_stream.finish(run_id, ok=False, reason=result.reason)
        return result

    parts = (result.manifest.get("parts") or [])[:MAX_PARTS]
    build_stream.emit(
        run_id,
        {
            "phase": "assembling",
            "total": len(parts),
            "name": result.manifest.get("name", ""),
            "seconds": round(result.seconds, 1),
        },
    )

    for index in range(1, len(parts) + 1):
        partial = {**result.manifest, "parts": parts[:index]}
        try:
            data, _, _ = build(partial)
        except ValueError:
            # A prefix that does not stand on its own is not a failure of the
            # whole build — the finished scene is already known to be valid.
            continue
        build_stream.emit(
            run_id,
            {
                "phase": "part",
                "index": index,
                "total": len(parts),
                "part": str(parts[index - 1].get("name") or parts[index - 1].get("shape") or ""),
                "data_url": to_data_url(data),
            },
        )

    # The final event carries what the page needs to settle: the finished
    # model, the parts list for the spoiler, and the summary line. Without it
    # the poller would have the geometry but no way to render the result
    # panel, and would need a second round trip to fetch what the build
    # already had in hand.
    build_stream.emit(
        run_id,
        {
            "phase": "done",
            "total": len(parts),
            "data_url": result.data_url,
            "manifest": result.manifest,
            "notes": result.notes,
            "part_count": result.part_count,
            "seconds": round(result.seconds, 1),
            "usd": round(result.usd, 4),
        },
    )
    build_stream.finish(run_id, ok=True)
    return result


def _finish(scene: Dict[str, Any], measured: Dict[str, Any]) -> SculptResult:
    """Scene dict -> GLB, shared by every provider.

    Deliberately after the provider branch: the clamping, the part budget and
    the geometry are the same work whoever produced the parts list, and a
    second copy of it would be a second place for the ceilings to drift.
    """
    try:
        data, notes, used = build(scene)
    except ValueError as exc:
        return SculptResult(ok=False, reason=str(exc), **measured)

    triangles, palette = measure(scene, data)
    return SculptResult(
        ok=True,
        glb=data,
        data_url=to_data_url(data),
        manifest=scene,
        notes=notes,
        part_count=used,
        triangles=triangles,
        palette=palette,
        **measured,
    )
