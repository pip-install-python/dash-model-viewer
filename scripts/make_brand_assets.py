#!/usr/bin/env python3
"""Generate every brand image from one geometry.

    python scripts/make_brand_assets.py

Writes:

    assets/logo.png                        header mark, 256px, transparent
    assets/favicon.ico                     16/32/48 multi-size
    assets/favicon/favicon-16x16.png
    assets/favicon/favicon-32x32.png
    assets/favicon/favicon-96x96.png
    assets/favicon/favicon.ico
    assets/favicon/apple-touch-icon.png    180px, opaque (iOS ignores alpha)
    assets/favicon/android-chrome-192x192.png
    assets/favicon/android-chrome-512x512.png
    github_assets/card-artwork.png         512px, for the social card

TWO MARKS, ON PURPOSE
---------------------
The social card is viewed at ~430px, so it uses the **wireframe** cube inside AR
framing brackets — the two things the package is, legible at that size.

A wireframe is mush at 16px, so the favicon and the header mark are a **solid**
isometric cube: three faces, three shades of the brand indigo. It reads at
16px, which is the only size that actually matters for a favicon.

Both come from the same hexagon, so they cannot drift apart.

WHY NOT scripts/make_favicons.py
--------------------------------
The network boilerplate ships `make_favicons.py`, which resamples one source
PNG into the same eight files. This repo deliberately does NOT carry it: the
mark here is *generated from geometry*, so there is no source PNG to resample,
and a second script writing the same eight paths from a different input is how
the browser icons and the crawler's icons drift apart without anyone noticing —
they stay byte-identical right up until one is regenerated and the other is not.
The output layout is the standard one either way, which is all that dimll's
icon discovery and `configure_seo(icons=[...])` actually care about.

Generated rather than committed-as-binaries because a binary nobody can
reproduce is the thing that rots. Pillow is a build-time dependency only — see
`make_social_card.py` for why it stays out of requirements.txt.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    sys.exit("This script needs Pillow:\n    pip install Pillow")

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "assets"
FAVICON_DIR = ASSETS / "favicon"
GITHUB_ASSETS = REPO_ROOT / "github_assets"

SS = 4  # supersample factor; Pillow has no anti-aliased polygon/line drawing

# Mantine indigo, matching PRIMARY_COLOR and the manifest's theme_color.
TOP_FACE = (116, 143, 252, 255)     # indigo 4 — lit from above
LEFT_FACE = (76, 110, 245, 255)     # indigo 6 — the theme colour
RIGHT_FACE = (59, 91, 219, 255)     # indigo 7 — in shadow
EDGE = (26, 27, 30, 255)            # near-black, separates the faces
INDIGO = (76, 110, 245, 255)
INDIGO_DIM = (76, 110, 245, 110)
WHITE = (245, 246, 247, 255)
DARK_BG = (26, 27, 30, 255)         # manifest background_color


def _hexagon(cx: float, cy: float, r: float):
    """The six outer vertices of an isometric cube, plus its centre vertex."""
    w = r * math.sqrt(3) / 2
    return {
        "top": (cx, cy - r),
        "upper_right": (cx + w, cy - r / 2),
        "lower_right": (cx + w, cy + r / 2),
        "bottom": (cx, cy + r),
        "lower_left": (cx - w, cy + r / 2),
        "upper_left": (cx - w, cy - r / 2),
        "mid": (cx, cy),
    }


def _solid_cube(size: int, margin_ratio: float = 0.10) -> Image.Image:
    """Three shaded faces. This is the mark that survives 16x16."""
    box = size * SS
    img = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    r = (box / 2) * (1 - margin_ratio) / (math.sqrt(3) / 2) * 0.86
    p = _hexagon(box / 2, box / 2, r)
    edge = max(1, int(box * 0.012))

    faces = [
        ((p["upper_left"], p["top"], p["upper_right"], p["mid"]), TOP_FACE),
        ((p["upper_left"], p["mid"], p["bottom"], p["lower_left"]), LEFT_FACE),
        ((p["mid"], p["upper_right"], p["lower_right"], p["bottom"]), RIGHT_FACE),
    ]
    for points, fill in faces:
        draw.polygon(points, fill=fill, outline=EDGE, width=edge)

    return img.resize((size, size), Image.LANCZOS)


def _wireframe_cube_with_brackets(size: int) -> Image.Image:
    """The card mark: an open wireframe inside AR framing brackets."""
    box = size * SS
    img = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    w = 7 * SS

    inset, arm = 18 * SS, 62 * SS
    a, b = inset, box - inset
    for x, y, dx, dy in ((a, a, 1, 1), (b, a, -1, 1), (a, b, 1, -1), (b, b, -1, -1)):
        draw.line([(x, y), (x + dx * arm, y)], fill=INDIGO, width=w)
        draw.line([(x, y), (x, y + dy * arm)], fill=INDIGO, width=w)

    p = _hexagon(box / 2, box / 2, 150 * SS)
    draw.line([p["upper_left"], p["top"], p["upper_right"]], fill=INDIGO_DIM, width=w)
    draw.line([p["upper_left"], p["lower_left"]], fill=INDIGO_DIM, width=w)
    draw.line([p["upper_right"], p["lower_right"]], fill=INDIGO_DIM, width=w)
    draw.line([p["lower_left"], p["bottom"], p["lower_right"]], fill=WHITE, width=w)
    draw.line([p["mid"], p["top"]], fill=WHITE, width=w)
    draw.line([p["mid"], p["lower_left"]], fill=WHITE, width=w)
    draw.line([p["mid"], p["lower_right"]], fill=WHITE, width=w)
    draw.line([p["upper_left"], p["mid"]], fill=INDIGO, width=w)
    draw.line([p["upper_right"], p["mid"]], fill=INDIGO, width=w)

    return img.resize((size, size), Image.LANCZOS)


def _on_dark(mark: Image.Image, size: int, radius_ratio: float = 0.0) -> Image.Image:
    """Composite onto the manifest's background — iOS and Android ignore alpha."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    plate = Image.new("RGBA", (size, size), DARK_BG)
    if radius_ratio:
        mask = Image.new("L", (size * SS, size * SS), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, size * SS - 1, size * SS - 1],
            radius=int(size * SS * radius_ratio), fill=255,
        )
        plate.putalpha(mask.resize((size, size), Image.LANCZOS))
    canvas = Image.alpha_composite(canvas, plate)
    inner = mark.resize((int(size * 0.72),) * 2, Image.LANCZOS)
    offset = (size - inner.width) // 2
    canvas.alpha_composite(inner, (offset, offset))
    return canvas


def main() -> int:
    ASSETS.mkdir(exist_ok=True)
    FAVICON_DIR.mkdir(parents=True, exist_ok=True)
    GITHUB_ASSETS.mkdir(exist_ok=True)
    written = []

    def save(img: Image.Image, path: Path, **kw) -> None:
        img.save(path, **kw)
        written.append((path.relative_to(REPO_ROOT), path.stat().st_size))

    master = _solid_cube(512)

    save(master.resize((256, 256), Image.LANCZOS), ASSETS / "logo.png")

    for px in (16, 32, 96):
        save(master.resize((px, px), Image.LANCZOS),
             FAVICON_DIR / f"favicon-{px}x{px}.png")

    ico_sizes = [(16, 16), (32, 32), (48, 48)]
    save(master, ASSETS / "favicon.ico", format="ICO", sizes=ico_sizes)
    save(master, FAVICON_DIR / "favicon.ico", format="ICO", sizes=ico_sizes)

    # iOS composites onto white if the icon is transparent, which turns a dark
    # mark into a pale smudge. Give it an opaque plate.
    save(_on_dark(master, 180, radius_ratio=0.0), FAVICON_DIR / "apple-touch-icon.png")
    for px in (192, 512):
        save(_on_dark(master, px, radius_ratio=0.16),
             FAVICON_DIR / f"android-chrome-{px}x{px}.png")

    save(_wireframe_cube_with_brackets(512), GITHUB_ASSETS / "card-artwork.png")

    for path, size in written:
        print(f"  {size:>8,}  {path}")
    print(f"\n{len(written)} files. Rerun scripts/make_social_card.py to pick up the artwork.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
