"""Drape one image across a whole sculpture — a front planar projection.

WHY A PROJECTION AND NOT PER-PRIMITIVE UVs
------------------------------------------
The owner's ask was to take the image that produced a sculpture and lay it over
the result, "in a similar way as to /texture-upload". The obvious
implementation — give every primitive the unit square — repeats the entire photo
on every box, cylinder and sphere, which reads as thirty small photos rather
than one object wearing one. What is wanted is the image projected onto the
model the way a slide projector throws it: computed from WORLD position, after
placement, across the model's front-facing rectangle.

That also makes the projection independent of how the model is built. It does
not care whether a part is a box or a torus, whether it was placed directly or
expanded from a `ref`, or how many parts there are. Add hierarchy later and the
projection still drapes once, because it reads finished geometry.

WHAT IT COSTS, STATED HERE BECAUSE THE PAGE STATES IT TOO
--------------------------------------------------------
glTF multiplies `baseColorFactor` into `baseColorTexture`, so a part keeping its
generated colour would tint the photo — a brown crate would stain its patch of
the image brown. Textured parts therefore get a WHITE base colour and the
photograph shows true. Everything else about the surface survives: metallic,
roughness and emissive are per part and are left alone, so a glowing part still
glows under the texture. Turning the texture off restores the colours exactly.

THE MANIFEST STAYS TEXTURELESS. Draping happens at RENDER time, never in the
scene description, so a manifest's bytes are the same whether or not it was
ever draped, and a `.glb` saved untextured is byte-identical to one built before
the feature existed.
"""

from __future__ import annotations

import io
from typing import List, Optional, Sequence, Tuple

from lib import glb

#: Longest edge of the baked texture. 640 is `lib/relief.py`'s number and is
#: kept the same deliberately: both features embed an image in a `.glb` that has
#: to survive `MAX_GLB_BYTES` and a `data:` URL, and two different answers to
#: the same question is how a cap silently becomes two caps.
MAX_TEXTURE_PX = 640

#: White, so the photograph shows true rather than tinted by the part.
NEUTRAL = (1.0, 1.0, 1.0, 1.0)


def prepare(raw: bytes) -> bytes:
    """Decode any accepted upload and return an optimised PNG under the cap.

    Pillow is already a declared dependency (`lib/relief.py`), and it is what
    makes this safe: the bytes are decoded and re-encoded rather than passed
    through, so whatever arrives leaves as a plain raster.
    """
    from PIL import Image

    with Image.open(io.BytesIO(raw)) as src:
        image = src.convert("RGB")
        image.thumbnail((MAX_TEXTURE_PX, MAX_TEXTURE_PX), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def bounds(meshes: Sequence[glb.Mesh]) -> Optional[Tuple[float, float, float, float]]:
    """The model's front-facing rectangle in world space: (min_x, min_y, max_x, max_y)."""
    xs: List[float] = []
    ys: List[float] = []
    for mesh in meshes:
        for x, y, _z in glb.world_positions(mesh):
            xs.append(x)
            ys.append(y)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def drape(meshes: Sequence[glb.Mesh], image: bytes) -> int:
    """Project `image` across `meshes` in place. Returns how many were draped.

    The whole model shares one rectangle, so the parts together carry one
    picture — a part covering the left third of the silhouette gets the left
    third of the photo.
    """
    box = bounds(meshes)
    if box is None:
        return 0
    min_x, min_y, max_x, max_y = box
    # A perfectly flat model in either axis would divide by zero. Fall back to
    # 1 m rather than refusing: a plane is a legitimate thing to drape.
    width = (max_x - min_x) or 1.0
    height = (max_y - min_y) or 1.0

    draped = 0
    for mesh in meshes:
        mesh.uvs = [
            # v is measured DOWN from the top: glTF's texture origin is the
            # image's upper-left, so the top of the model must take the top of
            # the picture or every sculpture wears its photo upside down.
            ((x - min_x) / width, (max_y - y) / height)
            for x, y, _z in glb.world_positions(mesh)
        ]
        mesh.material.base_color = list(NEUTRAL)
        mesh.material.texture_png = image
        draped += 1
    return draped
