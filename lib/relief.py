"""Image → a real `.glb`, with Claude reading the picture and code cutting it.

WHAT THIS IS, STATED PLAINLY
----------------------------
This is **not** photogrammetry and not neural reconstruction. One photograph
does not contain the back of an object, and nothing here pretends otherwise.

What it does is carve a **relief** — a bas-relief slab, the way a coin or a
carved panel is 3D. The image's luminance becomes height, the image itself
becomes the surface texture, and the result is a solid object you can orbit,
light and place in AR. For faces, logos, leaves, coins, lettering and hand-drawn
shapes that is genuinely the right answer, and it works on any image with no
generation cost at all.

WHERE THE MODEL EARNS ITS PLACE
-------------------------------
The geometry is pure arithmetic — but the *parameters* are a judgement call, and
the wrong ones produce a puddle or a cliff. Deciding whether a photo is a coin
(shallow, stepped, metallic) or a leaf (soft, smooth, matte) requires looking at
it. So Claude looks at it — vision in, structured parameters out — and code does
everything after.

It also writes the `alt` text, which `ModelViewer` requires and which is the
whole experience for a screen-reader user.

FULL 360° IS A DIFFERENT PIPELINE
---------------------------------
To get all sides you must *generate* the unseen ones. The SailsBoard object
generator does exactly that: front view in, five more orthographic views out,
each conditioned on the front as an identity lock plus the already-approved
views for consistency. Those six views are precisely the six faces of a textured
box — a cube impostor. It is a good pipeline and it costs one image-generation
call per view. This page deliberately does the zero-generation half.
"""

from __future__ import annotations

import base64
import io
import json
import math
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from lib import glb

MODEL = "claude-opus-5"
MAX_TOKENS = 1200
EFFORT = "low"

#: Mesh resolution. 120x120 is ~28k triangles — detailed enough for a face,
#: small enough to stay inside the data-URL ceiling with a texture attached.
GRID = 120
#: The embedded texture is resized to this before encoding.
TEXTURE_PX = 640
#: Longest edge of the finished object, in metres. AR wants a real-world size.
TARGET_SIZE_M = 0.30

MAX_UPLOAD_BYTES = 6_000_000
PROFILES = ("linear", "soft", "punchy", "stepped")
#: What to do with a flat background. The single most important parameter, and
#: the one that is not obvious: on a photo shot against white, brightness-as-
#: height makes the BACKGROUND the highest part of the carving and sinks the
#: subject into it. The result is a flat plateau with a subject-shaped dent —
#: which is why the first version of this page rendered as a blank slab.
BACKGROUNDS = ("keep", "cut_light", "cut_dark", "alpha")


@dataclass
class ReliefResult:
    ok: bool
    reason: str = ""
    glb: bytes = b""
    data_url: str = ""
    title: str = ""
    alt: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


# --------------------------------------------------------------------------
# Vision → parameters
# --------------------------------------------------------------------------

SYSTEM = """You are setting up a bas-relief carving of a photograph. The
image's brightness becomes height: bright pixels rise, dark pixels stay low.
Look at the picture and choose the carving parameters.

depth_profile — how brightness maps to height:
  linear   even. Good for gradients and soft photographic subjects.
  soft     compresses highlights. Use when a few bright spots would otherwise
           become spikes — glare, specular highlights, a white background.
  punchy   expands the bright end. Use for flat art, logos and lettering where
           you want a crisp raised shape rather than a gentle mound.
  stepped  quantises into flat terraces. Use for coins, medallions, stamps,
           woodcuts and anything that reads as carved rather than moulded.

depth_scale — relief depth as a fraction of the object's width, 0.02 to 0.30.
  A coin is about 0.04. A carved panel about 0.12. Above 0.20 it stops reading
  as a relief and starts reading as terrain.

background — what to do with a flat, uniform backdrop. READ THIS ONE CAREFULLY;
  it matters more than every other parameter here:
    cut_light  the subject sits on a LIGHT backdrop (white paper, a studio
               sweep, a blown-out sky). The backdrop is cut down to the base
               plate so the subject stands proud of it. Right for most product
               shots, posters, scanned art and logos.
    cut_dark   the subject sits on a DARK backdrop.
    alpha      the image already carries transparency; use it.
    keep       there is no separable backdrop — a landscape, a texture, a
               full-bleed photograph. Every pixel is subject.
  Choosing `keep` on a white-background photo makes the BACKGROUND the tallest
  part of the carving and sinks the subject into it, so the whole thing reads as
  a blank slab. If the corners are all one flat colour, CUT.

invert — true when the SUBJECT'S OWN dark tones are what should stand proud:
  black ink line art, an engraved plate, a silhouette. This is about the
  subject's tones, not about the backdrop — `background` handles that.

metallic / roughness — the material of the FINISHED CARVING, not of the thing
  photographed. A bronze coin is metallic 1.0, roughness 0.35. Carved stone or
  paper is metallic 0.0, roughness 0.85.

title — three words or fewer.
alt — one sentence describing the image for someone who cannot see it. This is
  an accessibility requirement, not a caption: say what is depicted, not that it
  is a 3D model.
notes — one short sentence on why you chose this profile."""


def _schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "alt": {"type": "string"},
            "depth_profile": {"type": "string", "enum": list(PROFILES)},
            "depth_scale": {"type": "number"},
            "invert": {"type": "boolean"},
            "background": {"type": "string", "enum": list(BACKGROUNDS)},
            "metallic": {"type": "number"},
            "roughness": {"type": "number"},
            "notes": {"type": "string"},
        },
        "required": ["title", "alt", "depth_profile", "depth_scale", "invert",
                     "background", "metallic", "roughness", "notes"],
        "additionalProperties": False,
    }


DEFAULT_PARAMS: Dict[str, Any] = {
    "title": "Relief",
    "alt": "A bas-relief carved from an uploaded image.",
    "depth_profile": "soft",
    "depth_scale": 0.10,
    "invert": False,
    "background": "cut_light",
    "metallic": 0.0,
    "roughness": 0.8,
    "notes": "Defaults — no model analysis was available.",
}


def analyse(image_bytes: bytes, media_type: str) -> Tuple[Dict[str, Any], List[str]]:
    """Claude looks at the image and returns carving parameters."""
    notes: List[str] = []
    if not available():
        notes.append("no ANTHROPIC_API_KEY — carved with defaults")
        return dict(DEFAULT_PARAMS), notes

    try:
        import anthropic
    except ImportError:
        notes.append("anthropic not installed — carved with defaults")
        return dict(DEFAULT_PARAMS), notes

    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            output_config={
                "effort": EFFORT,
                "format": {"type": "json_schema", "schema": _schema()},
            },
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": base64.b64encode(image_bytes).decode("ascii"),
                    }},
                    {"type": "text", "text": "Choose the carving parameters."},
                ],
            }],
        )
    except Exception as exc:  # noqa: BLE001
        notes.append(f"analysis failed ({type(exc).__name__}) — carved with defaults")
        return dict(DEFAULT_PARAMS), notes

    if response.stop_reason == "refusal":
        notes.append("analysis declined by the safety system — carved with defaults")
        return dict(DEFAULT_PARAMS), notes

    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        params = json.loads(text)
    except ValueError:
        notes.append("analysis returned unusable JSON — carved with defaults")
        return dict(DEFAULT_PARAMS), notes

    merged = dict(DEFAULT_PARAMS)
    merged.update({k: v for k, v in params.items() if v is not None})
    return merged, notes


# --------------------------------------------------------------------------
# Parameters → geometry (deterministic, no model involved)
# --------------------------------------------------------------------------


def _apply_profile(v: float, profile: str) -> float:
    if profile == "soft":
        return math.sqrt(v)
    if profile == "punchy":
        return v * v
    if profile == "stepped":
        return round(v * 6) / 6
    return v


def carve(image_bytes: bytes, params: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
    """Build the relief. Pure — same image and params give the same bytes."""
    from PIL import Image, ImageOps

    src = Image.open(io.BytesIO(image_bytes))
    src = ImageOps.exif_transpose(src).convert("RGBA")

    aspect = src.width / max(1, src.height)
    if aspect >= 1:
        gw, gh = GRID, max(8, int(GRID / aspect))
    else:
        gw, gh = max(8, int(GRID * aspect)), GRID

    heights_img = src.convert("L").resize((gw, gh), Image.LANCZOS)
    alpha = src.getchannel("A").resize((gw, gh), Image.LANCZOS)
    lum = list(heights_img.getdata())
    alp = list(alpha.getdata())

    invert = bool(params.get("invert"))
    profile = params.get("depth_profile", "soft")
    if profile not in PROFILES:
        profile = "soft"

    lo, hi = min(lum), max(lum)
    span = max(1, hi - lo)

    # --- backdrop mask ----------------------------------------------------
    # The bug this fixes: with brightness-as-height, a subject photographed on
    # white makes the BACKGROUND the tallest part of the carving and sinks the
    # subject into it. The object renders as a blank slab with a subject-shaped
    # dent — which is exactly what the first version of this page produced.
    #
    # The reference tone is sampled from the border rather than assumed, so
    # "light" means "whatever this image's edges actually are".
    mode = params.get("background", "cut_light")
    if mode not in BACKGROUNDS:
        mode = "cut_light"

    border = (
        [lum[ix] for ix in range(gw)]
        + [lum[(gh - 1) * gw + ix] for ix in range(gw)]
        + [lum[iy * gw] for iy in range(gh)]
        + [lum[iy * gw + gw - 1] for iy in range(gh)]
    )
    border.sort()
    reference = border[len(border) // 2]
    tolerance = 26  # 0-255; loose enough for JPEG noise and a soft vignette

    def is_backdrop(i: int) -> bool:
        if mode == "alpha":
            return alp[i] < 24
        if mode == "cut_light":
            return lum[i] >= reference - tolerance and reference > 140
        if mode == "cut_dark":
            return lum[i] <= reference + tolerance and reference < 115
        return False

    def height_at(ix: int, iy: int) -> float:
        i = iy * gw + ix
        if is_backdrop(i):
            return 0.0
        v = (lum[i] - lo) / span
        if invert:
            v = 1.0 - v
        v = _apply_profile(v, profile)
        # Fully transparent pixels carve down to the backplate rather than
        # standing proud of it — otherwise a cut-out PNG grows a solid border.
        return v * (alp[i] / 255.0)

    width_m = TARGET_SIZE_M if aspect >= 1 else TARGET_SIZE_M * aspect
    height_m = TARGET_SIZE_M / aspect if aspect >= 1 else TARGET_SIZE_M
    depth_m = max(0.02, min(0.30, float(params.get("depth_scale", 0.1)))) * width_m
    back_m = depth_m * 0.25  # a slab, so it is an object rather than a sheet

    positions: List[Tuple[float, float, float]] = []
    uvs: List[Tuple[float, float]] = []
    indices: List[int] = []

    # Front surface, displaced.
    for iy in range(gh):
        for ix in range(gw):
            u = ix / (gw - 1)
            v = iy / (gh - 1)
            positions.append((
                (u - 0.5) * width_m,
                (0.5 - v) * height_m,
                height_at(ix, iy) * depth_m,
            ))
            uvs.append((u, v))
    for iy in range(gh - 1):
        for ix in range(gw - 1):
            a = iy * gw + ix
            b = a + 1
            c = a + gw
            d = c + 1
            indices.extend([a, c, b, b, c, d])

    # Flat back, and a rim joining the two so the slab is closed.
    back_base = len(positions)
    for iy in range(gh):
        for ix in range(gw):
            u = ix / (gw - 1)
            v = iy / (gh - 1)
            positions.append(((u - 0.5) * width_m, (0.5 - v) * height_m, -back_m))
            uvs.append((u, v))
    for iy in range(gh - 1):
        for ix in range(gw - 1):
            a = back_base + iy * gw + ix
            b = a + 1
            c = a + gw
            d = c + 1
            indices.extend([a, b, c, b, d, c])

    def rim(seq: List[int]) -> None:
        for k in range(len(seq) - 1):
            f0, f1 = seq[k], seq[k + 1]
            b0, b1 = f0 + back_base, f1 + back_base
            indices.extend([f0, f1, b0, f1, b1, b0])

    top = [ix for ix in range(gw)]
    bottom = [(gh - 1) * gw + ix for ix in reversed(range(gw))]
    left = [iy * gw for iy in reversed(range(gh))]
    right = [iy * gw + (gw - 1) for iy in range(gh)]
    rim(top)
    rim(right)
    rim(bottom)
    rim(left)

    texture = src.convert("RGB")
    texture.thumbnail((TEXTURE_PX, TEXTURE_PX), Image.LANCZOS)
    buf = io.BytesIO()
    texture.save(buf, format="PNG", optimize=True)

    material = glb.Material(
        base_color=(1.0, 1.0, 1.0, 1.0),   # white, so the texture shows true
        metallic=max(0.0, min(1.0, float(params.get("metallic", 0.0)))),
        roughness=max(0.05, min(1.0, float(params.get("roughness", 0.8)))),
        name="relief",
        texture_png=buf.getvalue(),
        double_sided=False,
    )

    mesh = glb.Mesh(positions, indices, None, uvs, material,
                    translation=(0.0, height_m / 2, 0.0), name="relief")
    data = glb.GLBBuilder().add(mesh).build()

    stats = {
        "grid": f"{gw}x{gh}",
        "triangles": len(indices) // 3,
        "size_m": [round(width_m, 3), round(height_m, 3), round(depth_m + back_m, 3)],
        "glb_bytes": len(data),
        "texture_px": list(texture.size),
    }
    return data, stats


def to_data_url(data: bytes) -> str:
    return "data:model/gltf-binary;base64," + base64.b64encode(data).decode("ascii")


def relief_from_image(image_bytes: bytes, media_type: str = "image/png") -> ReliefResult:
    if not image_bytes:
        return ReliefResult(ok=False, reason="No image was uploaded.")
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        return ReliefResult(
            ok=False,
            reason=f"That image is {len(image_bytes) / 1e6:.1f} MB; the limit is "
                   f"{MAX_UPLOAD_BYTES / 1e6:.0f} MB.",
        )
    if media_type not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
        return ReliefResult(ok=False, reason=f"Unsupported image type {media_type!r}.")

    params, notes = analyse(image_bytes, media_type)
    try:
        data, stats = carve(image_bytes, params)
    except Exception as exc:  # noqa: BLE001
        return ReliefResult(ok=False, reason=f"Carving failed: {type(exc).__name__}: {exc}")

    return ReliefResult(
        ok=True,
        glb=data,
        data_url=to_data_url(data),
        title=str(params.get("title") or "Relief")[:60],
        alt=str(params.get("alt") or DEFAULT_PARAMS["alt"])[:300],
        params=params,
        notes=notes,
        stats=stats,
    )
