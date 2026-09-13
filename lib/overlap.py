"""How much a sculpture's parts interpenetrate, measured from geometry alone.

WHY THIS EXISTS
---------------
The owner's words were "a lot of rigid shapes … make them less rigid and able
to blend better together". Measured on the lighthouse sample, the cause is not
tessellation: the tower's top is at y=2.000 and the lamp's bottom at y=2.010, a
10 mm GAP. Parts abut instead of interpenetrating, and the prompt never told the
model that interpenetration was allowed — `git grep` for overlap/intersect/
merge/blend in the runtime prompt returned nothing.

"Blend better" is a judgement. This turns it into a number: of the part pairs
that come close enough to read as joined, what fraction actually OVERLAP rather
than leaving a gap? That is the figure G1's before/after table carries, and it
separates what the prompt's new guidance bought from what the v2 vocabulary
bought.

EXTENTS COME FROM THE BUILT GEOMETRY, NOT FROM A SECOND COPY OF THE SIZE RULES.
It would be quicker to compute a bounding box from `size` directly, and that is
how note 197 happened: a second place that believed `size.x` was a radius. So
each part is built with the same dispatch the renderer uses and its vertices are
measured. No rendering, no file — just the vertex arrays.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from lib import glb, sculptor

#: Two parts whose boxes are within this distance are "at a joint" — close
#: enough that a viewer reads them as touching. Pairs further apart than this
#: are unrelated and are not counted either way.
JOINT_TOLERANCE_M = 0.02

Box = Tuple[Tuple[float, float, float], Tuple[float, float, float]]


def _rotate(point: Tuple[float, float, float],
            quat: List[float]) -> Tuple[float, float, float]:
    """Rotate a point by a quaternion (x, y, z, w)."""
    x, y, z = point
    qx, qy, qz, qw = quat
    # t = 2 * (q_vec x p)
    tx = 2.0 * (qy * z - qz * y)
    ty = 2.0 * (qz * x - qx * z)
    tz = 2.0 * (qx * y - qy * x)
    return (
        x + qw * tx + (qy * tz - qz * ty),
        y + qw * ty + (qz * tx - qx * tz),
        z + qw * tz + (qx * ty - qy * tx),
    )


def _mesh_for(part: Dict[str, Any]) -> Optional[glb.Mesh]:
    """Build one part with the renderer's own dispatch, or None if unusable."""
    shape = str(part.get("shape", "")).lower()
    if shape not in sculptor.SHAPES:
        return None
    size = part.get("size") or {}
    w = float(size.get("x", 0.5))
    h = float(size.get("y", 0.5))
    d = float(size.get("z", 0.5))
    kw: Dict[str, Any] = dict(material=glb.Material(), name="probe")
    if shape == "box":
        return glb.box(w, h, d, **kw)
    if shape == "sphere":
        return glb.sphere(w / 2, **kw)
    if shape == "cylinder":
        return glb.cylinder(w / 2, h, **kw)
    if shape == "cone":
        return glb.cone(w / 2, h, **kw)
    if shape == "torus":
        return glb.torus(w / 2, max(0.005, d / 2), **kw)
    return glb.plane(w, d, **kw)


def aabb(part: Dict[str, Any]) -> Optional[Box]:
    """The part's axis-aligned bounding box in world coordinates.

    Rotation is applied, so a tilted part's box is the box of the tilted
    geometry rather than of its untilted size — which is the difference between
    a useful adjacency measurement and a misleading one.
    """
    mesh = _mesh_for(part)
    if mesh is None or not mesh.positions:
        return None
    rot = part.get("rotation") or {}
    quat = glb._euler_to_quat(
        float(rot.get("x", 0.0)), float(rot.get("y", 0.0)), float(rot.get("z", 0.0))
    )
    pos = part.get("position") or {}
    ox = float(pos.get("x", 0.0))
    oy = float(pos.get("y", 0.0))
    oz = float(pos.get("z", 0.0))

    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for point in mesh.positions:
        rx, ry, rz = _rotate(point, quat)
        for i, v in enumerate((rx + ox, ry + oy, rz + oz)):
            lo[i] = min(lo[i], v)
            hi[i] = max(hi[i], v)
    return ((lo[0], lo[1], lo[2]), (hi[0], hi[1], hi[2]))


def _separation(a: Box, b: Box) -> float:
    """Distance between two boxes. Negative means they interpenetrate.

    Per axis: the gap if they are apart, the negative of the shared span if
    they overlap. The pair overlaps only when EVERY axis overlaps, so the
    separation is the largest per-axis value.
    """
    worst = -math.inf
    for i in range(3):
        gap = max(a[0][i] - b[1][i], b[0][i] - a[1][i])
        worst = max(worst, gap)
    return worst


def report(manifest: Dict[str, Any],
           tolerance: float = JOINT_TOLERANCE_M) -> Dict[str, Any]:
    """Interpenetration across one sculpture.

    Returns counts and the pairs, so a report can name which joints are gaps
    rather than only quoting a fraction.
    """
    parts = [p for p in (manifest.get("parts") or []) if isinstance(p, dict)]
    boxes = [(p.get("name") or f"part{i}", aabb(p)) for i, p in enumerate(parts)]
    boxes = [(n, b) for n, b in boxes if b is not None]

    overlaps: List[Tuple[str, str, float]] = []
    gaps: List[Tuple[str, str, float]] = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (na, ba), (nb, bb) = boxes[i], boxes[j]
            sep = _separation(ba, bb)
            # STRICTLY less than zero. Exact tangency — a column resting on a
            # floor at separation 0.0 — counts as a GAP, not an overlap, and
            # that is the whole point of the measurement: two surfaces that
            # merely meet read as two objects stacked, which is the rigidity
            # the owner described. A part sunk even a millimetre in reads as
            # one mass. (-0.0 < 0.0 is False in IEEE arithmetic, so tangency
            # lands on the gap side without a special case.)
            if sep < 0.0:
                overlaps.append((na, nb, sep))
            elif sep <= tolerance:
                gaps.append((na, nb, sep))

    joints = len(overlaps) + len(gaps)
    return {
        "parts": len(boxes),
        "joints": joints,
        "overlapping": len(overlaps),
        "gapped": len(gaps),
        # None rather than 0.0 when there are no joints at all: a sculpture of
        # scattered parts has no interpenetration rate, and reporting 0%
        # would read as a failure to blend rather than as nothing to blend.
        "rate": (len(overlaps) / joints) if joints else None,
        "overlap_pairs": overlaps,
        "gap_pairs": gaps,
    }


def summary(manifest: Dict[str, Any]) -> str:
    """One line for a results table."""
    r = report(manifest)
    if r["rate"] is None:
        return f"{r['parts']} parts, no joints within {JOINT_TOLERANCE_M * 100:.0f} cm"
    return (
        f"{r['overlapping']}/{r['joints']} joints interpenetrate "
        f"({r['rate'] * 100:.0f}%)"
    )
