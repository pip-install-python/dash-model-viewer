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

from lib import glb, spend

MODEL = "claude-opus-5"
MAX_TOKENS = 4000
EFFORT = "medium"

#: The vocabulary. Everything the model may build with, and nothing else.
SHAPES = ("box", "sphere", "cylinder", "cone", "torus", "plane")

#: Hard ceilings. A model asked for "a city" will happily emit 400 parts; at
#: ~1.5 KB of geometry each that is a data URL no browser will accept.
MAX_PARTS = 28
MAX_EXTENT = 4.0          # metres, any single dimension
MAX_SCENE_RADIUS = 5.0    # metres from origin
MAX_GLB_BYTES = 3_000_000

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


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


# --------------------------------------------------------------------------
# Prompt
# --------------------------------------------------------------------------

SYSTEM = f"""You compose 3D sculptures out of primitive shapes, for display in
Google's <model-viewer>. You are a scene compiler, not a modeller: you choose
shapes, places and materials, and code builds the geometry exactly.

THE VOCABULARY — you may use nothing else:
  box       size = width, height, depth
  sphere    size = radius (width used)
  cylinder  size = radius (width), height
  cone      size = radius (width), height
  torus     size = radius (width), tube thickness (depth)
  plane     size = width, depth   (a flat ground/backdrop card)

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


def _clamp(value: Any, low: float, high: float, default: float) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return default


def build(scene: Dict[str, Any]) -> Tuple[bytes, List[str], int]:
    """Turn a validated parts list into glb bytes. Pure, and unit-testable."""
    notes: List[str] = []
    parts = scene.get("parts") or []

    if len(parts) > MAX_PARTS:
        notes.append(f"kept the first {MAX_PARTS} of {len(parts)} parts")
        parts = parts[:MAX_PARTS]

    builder = glb.GLBBuilder()
    used = 0
    for i, part in enumerate(parts):
        shape = str(part.get("shape", "")).lower()
        if shape not in SHAPES:
            notes.append(f"dropped part {i} — unknown shape {shape!r}")
            continue

        size = part.get("size") or {}
        pos = part.get("position") or {}
        rot = part.get("rotation") or {}

        w = _clamp(size.get("x"), 0.01, MAX_EXTENT, 0.5)
        h = _clamp(size.get("y"), 0.01, MAX_EXTENT, 0.5)
        d = _clamp(size.get("z"), 0.01, MAX_EXTENT, 0.5)

        px = _clamp(pos.get("x"), -MAX_SCENE_RADIUS, MAX_SCENE_RADIUS, 0.0)
        py = _clamp(pos.get("y"), -MAX_SCENE_RADIUS, MAX_SCENE_RADIUS, 0.0)
        pz = _clamp(pos.get("z"), -MAX_SCENE_RADIUS, MAX_SCENE_RADIUS, 0.0)

        emissive_strength = _clamp(part.get("emissive_strength"), 0.0, 1.0, 0.0)
        colour = _colour(part.get("color", ""))
        material = glb.Material(
            base_color=colour,
            metallic=_clamp(part.get("metallic"), 0.0, 1.0, 0.0),
            roughness=_clamp(part.get("roughness"), 0.05, 1.0, 0.8),
            emissive=tuple(c * emissive_strength for c in colour),
            name=str(part.get("name") or f"part{i}")[:48],
        )

        kw = dict(
            material=material,
            translation=(px, py, pz),
            rotation_euler=(
                _clamp(rot.get("x"), -360, 360, 0.0),
                _clamp(rot.get("y"), -360, 360, 0.0),
                _clamp(rot.get("z"), -360, 360, 0.0),
            ),
            name=material.name,
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

        builder.add(mesh)
        used += 1

    if not used:
        raise ValueError("no usable parts in the scene")

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
) -> SculptResult:
    """One sculpt. The knobs are arguments so /benchmark can sweep them."""
    request = (request or "").strip()
    meta = dict(model=model, effort=effort, max_tokens=max_tokens)
    if not request:
        return SculptResult(ok=False, reason="Describe what you want sculpted.", **meta)
    if len(request) > 400:
        return SculptResult(ok=False, reason="Keep the request under 400 characters.", **meta)
    if enforce_budget:
        verdict = spend.check(1, spend.estimate_usd(model, max_tokens))
        if not verdict.allowed:
            return SculptResult(ok=False, reason=verdict.reason, **meta)
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

    prompt = request if not style else f"{request}\n\nStyle: {style}"
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
            system=SYSTEM,
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
