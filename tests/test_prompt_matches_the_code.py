"""The prompt is documentation that a MODEL reads, and it is pinned like a page.

Note 197: `lib/sculptor.py`'s prompt said `size = radius` for sphere, cylinder,
cone and torus while the dispatch passes `size.x / 2` to the builders. Every
curved part a model produced was half the size it intended; every box and plane
was exact. The silhouette came out right and only the curved masses were wrong,
which is invisible to read and nearly impossible to attribute by looking at the
result.

A page that disagrees with the code misleads a reader who can argue back. A
prompt that disagrees with the code misleads a model that cannot. So the prompt
gets the same treatment the page gets: one table in the code, both render from
it, and a test that the claim and the behaviour agree.
"""

from __future__ import annotations

import pathlib
import re

import pytest

import lib.glb as glb
from lib import sculptor

REPO = pathlib.Path(__file__).resolve().parent.parent
PAGE = REPO / "docs" / "scene-manifest" / "scene-manifest.md"


def _width_of(shape, x, y, z):
    """Build one part and measure its actual extent along X."""
    kw = dict(material=glb.Material(), translation=(0, 0, 0),
              rotation_euler=(0, 0, 0), name="t")
    mesh = {
        "box": lambda: glb.box(x, y, z, **kw),
        "sphere": lambda: glb.sphere(x / 2, **kw),
        "cylinder": lambda: glb.cylinder(x / 2, y, **kw),
        "cone": lambda: glb.cone(x / 2, y, **kw),
        "torus": lambda: glb.torus(x / 2, max(0.005, z / 2), **kw),
        "plane": lambda: glb.plane(x, z, **kw),
    }[shape]()
    xs = [p[0] for p in mesh.positions]
    return max(xs) - min(xs)


# --------------------------------------------------------------------------
# The bug itself, as a regression
# --------------------------------------------------------------------------


@pytest.mark.parametrize("shape", sculptor.HALVED_SHAPES)
def test_the_prompt_never_calls_a_halved_size_a_radius(shape):
    """THE REGRESSION. The dispatch halves size.x for these four, so calling it
    a radius in the prompt asks the model for something twice what it gets."""
    meaning = dict(sculptor.size_semantics_rows())[shape]
    assert "radius" not in meaning.lower(), (
        f"the prompt tells the model size.x is a radius for {shape}, but the "
        f"dispatch passes size.x / 2 — the part renders half the intended size"
    )


def test_the_word_radius_appears_nowhere_in_the_vocabulary_block():
    """Belt to the braces: the whole block, not just the table it renders."""
    block = sculptor.SYSTEM.split("THE VOCABULARY", 1)[1].split("\n\n", 1)[0]
    assert "radius" not in block.lower()


def test_the_prompt_says_size_is_a_full_width():
    """Saying what it is NOT is the half that prevents the error recurring from
    a model's own prior assumption."""
    assert "NEVER A RADIUS" in sculptor.SYSTEM
    assert "0.4m across" in sculptor.SYSTEM


# --------------------------------------------------------------------------
# The prompt's claims, measured against the geometry
# --------------------------------------------------------------------------


@pytest.mark.parametrize("shape", ["box", "sphere", "cylinder", "cone", "plane"])
def test_size_x_really_is_the_full_width_the_prompt_promises(shape):
    assert abs(_width_of(shape, 1.0, 1.0, 1.0) - 1.0) < 1e-9


def test_the_torus_width_is_the_sum_the_prompt_states():
    """The one shape where size.x alone is not the width — it is the RING
    diameter, and the tube stands out both sides."""
    for x, z in ((1.0, 1.0), (3.0, 0.2), (2.0, 0.4)):
        assert abs(_width_of("torus", x, 1.0, z) - (x + z)) < 1e-9
    assert "size.x + size.z" in sculptor.SYSTEM


# --------------------------------------------------------------------------
# One table, two renderings
# --------------------------------------------------------------------------


def test_every_shape_has_a_semantics_entry_both_ways():
    assert set(sculptor.SIZE_SEMANTICS) == set(sculptor.SHAPES)


def test_the_prompt_renders_the_table_rather_than_restating_it():
    """If the prompt were a literal, it could drift from the code again — which
    is exactly what happened."""
    source = (REPO / "lib" / "sculptor.py").read_text(encoding="utf-8")
    assert "_vocabulary_block()" in source
    for shape, meaning in sculptor.size_semantics_rows():
        assert meaning in sculptor.SYSTEM, f"{shape} is not in the rendered prompt"


def test_the_page_and_the_prompt_agree_shape_by_shape():
    """The page is markdown and cannot import, so it is compared rather than
    generated. Both must say the same thing about the same shape."""
    page = PAGE.read_text(encoding="utf-8")
    for shape, (sx, sy, sz) in sculptor.SIZE_SEMANTICS.items():
        row = next(line for line in page.splitlines()
                   if line.startswith(f"| `{shape}`"))
        cells = [c.strip().replace("**", "") for c in row.split("|")[2:5]]
        for cell, meaning in zip(cells, (sx, sy, sz)):
            if meaning is None:
                assert cell == "ignored", (
                    f"{shape}: the code ignores this component; the page says "
                    f"{cell!r}"
                )
            else:
                assert meaning in cell, (
                    f"{shape}: the code means {meaning!r}; the page says {cell!r}"
                )


def test_halved_shapes_are_exactly_those_the_dispatch_halves():
    """Read from the dispatch, so the list cannot go stale if a shape changes."""
    source = (REPO / "lib" / "sculptor.py").read_text(encoding="utf-8")
    dispatch = source.split("if shape == \"box\":", 1)[1].split("builder.add", 1)[0]
    halved = set(re.findall(r'shape == "(\w+)"', dispatch))
    halved |= {"plane"} if "else:  # plane" in dispatch else set()
    actually_halved = {
        s for s in sculptor.SHAPES
        if re.search(rf'glb\.{s}\(\s*w / 2', dispatch)
    }
    assert actually_halved == set(sculptor.HALVED_SHAPES), (
        f"the dispatch halves {sorted(actually_halved)}; HALVED_SHAPES says "
        f"{sorted(sculptor.HALVED_SHAPES)}"
    )
