"""Read, write and validate a scene manifest.

The manifest IS the sculpture: `lib.glb` is deterministic, so the same manifest
produces byte-identical `.glb` output. That is what makes export and import an
identity rather than an approximation, and it is why a generated sculpture can
be kept, edited by hand and rendered again without paying a model.

STRICTNESS IS THE POINT OF THE VERSION NUMBER. An unknown version is refused
rather than partially read, and within a known version an unknown KEY is
refused too — including inside `provenance`. If version 1 quietly ignored keys
it did not know, a version 2 manifest using part groups would be accepted by a
version 1 reader and render without them: a sculpture missing pieces, with
nothing said. The guarantee the number makes is only worth having if both doors
are shut.

EVERY BOUND IS IMPORTED FROM `lib.sculptor`, never restated. A documented limit
that disagrees with the enforced one is the defect class 1.0.0 spent its review
removing — `src`/`alt` were "required" in three places and checked in none.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from lib import glb, sculptor

#: The highest version this build understands, and the one a nested manifest
#: is written as.
VERSION = 2

#: Every version this build reads. A v1 manifest is not migrated on import: it
#: is read as v1 and renders exactly what it always rendered, which is what
#: makes the byte-hash regression on the committed samples meaningful.
READS = (1, 2)

#: What `from_scene` stamps on a model's output. THE LOWEST VERSION THAT CAN
#: EXPRESS THE SCULPTURE, not the highest this build knows: the schema a model
#: answers is flat, so its manifests are v1 and stay readable by anything that
#: only knows v1. Stamping 2 on a flat scene would narrow its audience and buy
#: nothing.
FLAT_VERSION = 1

#: Cap on an imported manifest, in bytes of JSON. A manifest for the maximum
#: 28 parts is roughly 8 KB, so this is generous by a wide margin and exists to
#: bound the parse, not to be reached.
MAX_JSON_BYTES = 256 * 1024

TOP_LEVEL = {"version", "parts", "name", "notes", "provenance"}
REQUIRED_TOP = {"version", "parts"}

#: v2 only. A v1 manifest carrying `defs` is refused by the same unknown-key
#: rule that refuses anything else it does not know — which is the point of
#: shutting both doors.
TOP_LEVEL_V2 = TOP_LEVEL | {"defs"}

#: A def is a part WITHOUT a position: it describes a thing, and a `ref` says
#: where that thing goes. Keeping position out is what makes every placement of
#: a def share one mesh and one material by construction rather than by a
#: comparison that could get it wrong.
DEF_PART_FIELDS = {"name", "shape", "size", "rotation", "color",
                   "metallic", "roughness", "emissive_strength"}

#: A group def holds children and nothing else; its placement comes from the
#: `ref` or the inline `group` that instantiates it.
DEF_GROUP_FIELDS = {"children"}

REF_REQUIRED = {"ref", "position"}
REF_OPTIONAL = {"rotation", "name"}

GROUP_REQUIRED = {"group", "position", "children"}
GROUP_OPTIONAL = {"rotation"}

#: The identity rotation, as glTF writes it.
IDENTITY_QUAT = [0.0, 0.0, 0.0, 1.0]

#: Defined, not free-form: an unknown key inside `provenance` reopens one level
#: down exactly the escape hatch the top level closes.
PROVENANCE_FIELDS = {"prompt": str, "model": str, "usd": (int, float), "generated": str}

PART_FIELDS = {
    "name", "shape", "size", "position", "rotation",
    "color", "metallic", "roughness", "emissive_strength",
}

VEC_FIELDS = {"size", "position", "rotation"}

#: (minimum, maximum) per scalar, read from the clamps in lib/sculptor.py so the
#: importer refuses exactly what the builder would silently clamp.
NUMBER_RANGES = {
    "metallic": (0.0, 1.0),
    "roughness": (0.05, 1.0),
    "emissive_strength": (0.0, 1.0),
}

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SLUG = re.compile(r"[^a-z0-9]+")


class ManifestError(ValueError):
    """Refused. The message names the field, so it is actionable."""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _vec(value: Any, where: str, lo: float, hi: float) -> None:
    if not isinstance(value, dict):
        raise ManifestError(f"{where}: expected an object with x, y and z")
    missing = {"x", "y", "z"} - set(value)
    if missing:
        raise ManifestError(f"{where}: missing {', '.join(sorted(missing))}")
    unknown = set(value) - {"x", "y", "z"}
    if unknown:
        raise ManifestError(f"{where}: unknown key {sorted(unknown)[0]!r}")
    for axis in ("x", "y", "z"):
        n = value[axis]
        if isinstance(n, bool) or not isinstance(n, (int, float)):
            raise ManifestError(f"{where}.{axis}: expected a number, got {type(n).__name__}")
        if not lo <= float(n) <= hi:
            raise ManifestError(f"{where}.{axis}: {n} is outside {lo} to {hi}")


def _part(part: Any, where: str) -> None:
    if not isinstance(part, dict):
        raise ManifestError(f"{where}: expected an object")

    unknown = set(part) - PART_FIELDS
    if unknown:
        raise ManifestError(f"{where}.{sorted(unknown)[0]}: unknown key")
    missing = PART_FIELDS - set(part)
    if missing:
        raise ManifestError(f"{where}: missing {', '.join(sorted(missing))}")

    shape = part["shape"]
    if shape not in sculptor.SHAPES:
        raise ManifestError(
            f"{where}.shape: {shape!r} is not one of "
            f"{', '.join(sculptor.SHAPES)}"
        )
    if not isinstance(part["name"], str):
        raise ManifestError(f"{where}.name: expected a string")

    _vec(part["size"], f"{where}.size", 0.01, sculptor.MAX_EXTENT)
    _vec(part["position"], f"{where}.position",
         -sculptor.MAX_SCENE_RADIUS, sculptor.MAX_SCENE_RADIUS)
    _vec(part["rotation"], f"{where}.rotation", -360.0, 360.0)

    if not isinstance(part["color"], str) or not _HEX.match(part["color"]):
        raise ManifestError(f"{where}.color: expected #RRGGBB, got {part['color']!r}")

    for field, (lo, hi) in NUMBER_RANGES.items():
        n = part[field]
        if isinstance(n, bool) or not isinstance(n, (int, float)):
            raise ManifestError(
                f"{where}.{field}: expected a number, got {type(n).__name__}"
            )
        if not lo <= float(n) <= hi:
            raise ManifestError(f"{where}.{field}: {n} is outside {lo} to {hi}")


def _def_part(value: Any, where: str) -> None:
    """A def describes a THING. Position is deliberately absent — see
    DEF_PART_FIELDS."""
    unknown = set(value) - DEF_PART_FIELDS
    if unknown:
        if sorted(unknown)[0] == "position":
            raise ManifestError(
                f"{where}.position: a def has no position — a `ref` says where "
                f"each placement goes. That is what lets every placement share "
                f"one mesh."
            )
        raise ManifestError(f"{where}.{sorted(unknown)[0]}: unknown key")
    missing = DEF_PART_FIELDS - set(value)
    if missing:
        raise ManifestError(f"{where}: missing {', '.join(sorted(missing))}")
    # Validated with a position bolted on, so a def's style obeys exactly the
    # rules a part's does and there is no second copy of them.
    _part(dict(value, position={"x": 0, "y": 0, "z": 0}), where)


def _placement(entry: Dict[str, Any], where: str, required: set, optional: set) -> None:
    unknown = set(entry) - required - optional
    if unknown:
        raise ManifestError(f"{where}.{sorted(unknown)[0]}: unknown key")
    missing = required - set(entry)
    if missing:
        raise ManifestError(f"{where}: missing {', '.join(sorted(missing))}")
    _vec(entry["position"], f"{where}.position",
         -sculptor.MAX_SCENE_RADIUS, sculptor.MAX_SCENE_RADIUS)
    if "rotation" in entry:
        _vec(entry["rotation"], f"{where}.rotation", -360.0, 360.0)
    if "name" in entry and not isinstance(entry["name"], str):
        raise ManifestError(f"{where}.name: expected a string")


def _entry(entry: Any, where: str, defs: Dict[str, Any],
           depth: int, stack: Tuple[str, ...]) -> None:
    """One item of `parts` or of a group's `children`: leaf, ref or group."""
    if not isinstance(entry, dict):
        raise ManifestError(f"{where}: expected an object")

    if "ref" in entry:
        _placement(entry, where, REF_REQUIRED, REF_OPTIONAL)
        name = entry["ref"]
        if not isinstance(name, str):
            raise ManifestError(f"{where}.ref: expected a string")
        if name not in defs:
            known = ", ".join(sorted(defs)) or "none are defined"
            raise ManifestError(f"{where}.ref: {name!r} is not in defs ({known})")
        if name in stack:
            raise ManifestError(
                f"{where}.ref: {name!r} contains itself — "
                f"{' -> '.join(stack + (name,))}"
            )
        target = defs[name]
        if "children" in target:
            _children(target["children"], f"defs.{name}.children",
                      defs, depth + 1, stack + (name,))
        return

    if "group" in entry:
        _placement(entry, where, GROUP_REQUIRED, GROUP_OPTIONAL)
        if not isinstance(entry["group"], str):
            raise ManifestError(f"{where}.group: expected a string")
        _children(entry["children"], f"{where}.children", defs, depth + 1, stack)
        return

    _part(entry, where)


def _children(children: Any, where: str, defs: Dict[str, Any],
              depth: int, stack: Tuple[str, ...]) -> None:
    if depth > sculptor.MAX_DEPTH:
        raise ManifestError(
            f"{where}: groups nest more than {sculptor.MAX_DEPTH} deep. "
            f"Deeper than that is almost always a sculpture repeating itself "
            f"rather than describing structure."
        )
    if not isinstance(children, list):
        raise ManifestError(f"{where}: expected an array")
    if not children:
        raise ManifestError(f"{where}: a group with no children renders nothing")
    for index, child in enumerate(children):
        _entry(child, f"{where}[{index}]", defs, depth, stack)


def _defs(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError("defs: expected an object")
    if len(value) > sculptor.MAX_DEFS:
        raise ManifestError(
            f"defs: {len(value)} entries, and the limit is {sculptor.MAX_DEFS}. "
            f"More than that is a parts bin rather than instancing."
        )
    for name, entry in value.items():
        where = f"defs.{name}"
        if not name or not isinstance(name, str):
            raise ManifestError("defs: every name must be a non-empty string")
        if not isinstance(entry, dict):
            raise ManifestError(f"{where}: expected an object")
        if "children" in entry:
            unknown = set(entry) - DEF_GROUP_FIELDS
            if unknown:
                raise ManifestError(f"{where}.{sorted(unknown)[0]}: unknown key")
        else:
            _def_part(entry, where)
    # Children are checked in a second pass: a def may reference another def
    # declared after it, and refusing that would make the file order-sensitive
    # for no reason.
    for name, entry in value.items():
        if "children" in entry:
            _children(entry["children"], f"defs.{name}.children", value, 1, (name,))
    return value


def _provenance(value: Any) -> None:
    if not isinstance(value, dict):
        raise ManifestError("provenance: expected an object")
    unknown = set(value) - set(PROVENANCE_FIELDS)
    if unknown:
        raise ManifestError(f"provenance.{sorted(unknown)[0]}: unknown key")
    for field, kind in PROVENANCE_FIELDS.items():
        if field not in value:
            continue
        n = value[field]
        if isinstance(n, bool) or not isinstance(n, kind):
            raise ManifestError(
                f"provenance.{field}: expected "
                f"{'a number' if field == 'usd' else 'a string'}"
            )
    if "usd" in value and float(value["usd"]) < 0:
        raise ManifestError(f"provenance.usd: {value['usd']} is negative")
    if "generated" in value and not _ISO_DATE.match(value["generated"]):
        raise ManifestError(
            f"provenance.generated: expected an ISO 8601 date (YYYY-MM-DD), "
            f"got {value['generated']!r}"
        )


def validate(manifest: Any) -> Dict[str, Any]:
    """Refuse anything this build cannot render exactly as written."""
    if not isinstance(manifest, dict):
        raise ManifestError("expected a JSON object at the top level")

    if "version" not in manifest:
        raise ManifestError("version: missing — this build writes and reads version 1")
    version = manifest["version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise ManifestError(f"version: expected an integer, got {type(version).__name__}")
    if version not in READS:
        readable = " and ".join(str(v) for v in READS)
        raise ManifestError(
            f"version: this manifest is version {version}; this build reads "
            f"version {readable}. It is not read partially — a newer manifest "
            f"may use shapes this build cannot render."
        )

    # v1 does not know `defs`, so a v1 manifest carrying one is refused by the
    # same unknown-key rule as anything else. That is deliberate: a v2 file
    # mislabelled as v1 must not render silently missing its instances.
    allowed = TOP_LEVEL_V2 if version >= 2 else TOP_LEVEL
    unknown = set(manifest) - allowed
    if unknown:
        key = sorted(unknown)[0]
        if key == "defs":
            raise ManifestError(
                "defs: version 1 has no defs — a manifest using defs, groups "
                "or refs is version 2."
            )
        raise ManifestError(f"{key}: unknown key")
    missing = REQUIRED_TOP - set(manifest)
    if missing:
        raise ManifestError(f"missing {', '.join(sorted(missing))}")

    for field in ("name", "notes"):
        if field in manifest and not isinstance(manifest[field], str):
            raise ManifestError(f"{field}: expected a string")
    if "provenance" in manifest:
        _provenance(manifest["provenance"])

    parts = manifest["parts"]
    if not isinstance(parts, list):
        raise ManifestError("parts: expected an array")

    if version == 1:
        if len(parts) > sculptor.MAX_PARTS:
            raise ManifestError(
                f"parts: {len(parts)} parts, and the limit is {sculptor.MAX_PARTS}"
            )
        for index, part in enumerate(parts):
            _part(part, f"parts[{index}]")
        return manifest

    defs = _defs(manifest["defs"]) if "defs" in manifest else {}
    for index, entry in enumerate(parts):
        _entry(entry, f"parts[{index}]", defs, 1, ())

    # THE LIMIT COUNTS LEAVES, NOT ENTRIES. A `ref` costs its def's leaf count
    # every time it is placed, so four refs to a five-part assembly are twenty
    # parts — which is what the renderer and the viewer actually carry.
    leaves = _count_leaves(parts, defs)
    if leaves > sculptor.MAX_PARTS:
        raise ManifestError(
            f"parts: {leaves} parts after expanding refs and groups, and the "
            f"limit is {sculptor.MAX_PARTS}"
        )
    return manifest


def _count_leaves(entries: List[Any], defs: Dict[str, Any]) -> int:
    total = 0
    for entry in entries:
        if "ref" in entry:
            target = defs[entry["ref"]]
            total += (_count_leaves(target["children"], defs)
                      if "children" in target else 1)
        elif "group" in entry:
            total += _count_leaves(entry["children"], defs)
        else:
            total += 1
    return total


def loads(text: str) -> Dict[str, Any]:
    """Parse and validate. The import path for a pasted manifest."""
    raw = text.encode("utf-8") if isinstance(text, str) else bytes(text)
    if len(raw) > MAX_JSON_BYTES:
        raise ManifestError(
            f"that manifest is {len(raw) / 1024:.0f} KB — the cap is "
            f"{MAX_JSON_BYTES // 1024} KB"
        )
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ManifestError(f"that is not valid JSON: {exc}") from exc
    return validate(parsed)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


ZERO_VEC = {"x": 0.0, "y": 0.0, "z": 0.0}


def _clamped_vec(value: Any, lo: float, hi: float) -> Tuple[float, float, float]:
    value = value or ZERO_VEC
    return tuple(
        max(lo, min(hi, float(value.get(axis, 0.0))))
        for axis in ("x", "y", "z")
    )


def expand(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten a manifest to the leaf placements a builder can draw.

    THE ONE THING THIS FILE DOES THAT IS NOT BOOKKEEPING. A nested manifest
    describes a sculpture as structure — a wheel defined once and placed four
    times, a lamp assembly lifted onto a tower — and the renderer draws leaves.
    Expansion is where the two meet.

    ROTATIONS COMPOSE AS QUATERNIONS, NEVER AS ADDED ANGLES. Euler angles do
    not add: a group turned about Y holding a part tilted about X is the
    ordinary case, and adding the two triples gives a different sculpture from
    the one that was written. The composed rotation is carried forward as a
    quaternion and handed to the builder as one, so there is no lossy trip back
    through Euler angles either.

    Returns one dict per leaf: the style to draw, where it goes, how it is
    turned, and — for anything reached through a `ref` — the key that makes
    every placement of the same def share ONE mesh and ONE material.
    """
    validated = validate(manifest)
    defs = validated.get("defs") or {}
    placements: List[Dict[str, Any]] = []

    def compose(origin, quat, entry):
        local = _clamped_vec(entry.get("position"),
                             -sculptor.MAX_SCENE_RADIUS, sculptor.MAX_SCENE_RADIUS)
        euler = _clamped_vec(entry.get("rotation"), -360.0, 360.0)
        if quat == IDENTITY_QUAT and origin == (0.0, 0.0, 0.0):
            # COMPOSING WITH THE IDENTITY MUST BE A NO-OP, and in IEEE
            # arithmetic it is not: `-0.0 + 0.0` is `+0.0`, so running a
            # top-level part through the general path rewrote a coordinate of
            # -0.0 as 0.0 and changed the file. Measured on colonnade.json,
            # whose columns sit on a circle and land exactly there. Identical
            # geometry, different bytes — and the v1 byte-hash guarantee is
            # the thing this whole version scheme is for.
            return local, glb._euler_to_quat(*euler)
        turned = glb.rotate_vector(local, quat)
        moved = tuple(
            # Clamped again after composing: the bound is on where a part
            # ENDS UP, and a child pushed outside the scene by its parent is
            # the case a local-only clamp would miss. Applying it twice is
            # idempotent, so a flat manifest is unaffected.
            max(-sculptor.MAX_SCENE_RADIUS,
                min(sculptor.MAX_SCENE_RADIUS, origin[i] + turned[i]))
            for i in range(3)
        )
        return moved, glb.quat_multiply(quat, glb._euler_to_quat(*euler))

    def walk(entries, origin, quat, share, depth):
        for index, entry in enumerate(entries):
            moved, turned = compose(origin, quat, entry)

            if "ref" in entry:
                name = entry["ref"]
                target = defs[name]
                if "children" in target:
                    walk(target["children"], moved, turned, f"def:{name}", depth + 1)
                else:
                    # The def's OWN rotation is its intrinsic orientation; the
                    # ref's is where this copy points. Both apply.
                    intrinsic = glb._euler_to_quat(
                        *_clamped_vec(target.get("rotation"), -360.0, 360.0))
                    placements.append({
                        "style": target,
                        "position": moved,
                        "quat": glb.quat_multiply(turned, intrinsic),
                        "share": f"def:{name}",
                        "name": entry.get("name") or target.get("name") or name,
                    })
            elif "group" in entry:
                walk(entry["children"], moved, turned,
                     f"{share}/g{index}" if share else None, depth + 1)
            else:
                placements.append({
                    "style": entry,
                    "position": moved,
                    "quat": turned,
                    # An inline part is its own thing even if two of them are
                    # identical: sharing is opt-in through `ref`, so a hand
                    # written manifest renders exactly as it reads.
                    "share": f"{share}/{index}" if share else None,
                    "name": entry.get("name") or f"part{index}",
                })

    walk(validated["parts"], (0.0, 0.0, 0.0), list(IDENTITY_QUAT), None, 1)
    return placements


def _ordered(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """`version` first, everything else alphabetical.

    Plain `sort_keys=True` would put `version` LAST — after name, notes, parts
    and provenance — and the version is the first thing a reader needs, because
    it decides whether the rest is even legible. So the order is fixed by hand
    at the top level and sorted below it, which is still fully deterministic.
    """
    out: Dict[str, Any] = {"version": manifest["version"]}
    for key in sorted(k for k in manifest if k != "version"):
        value = manifest[key]
        if key == "parts":
            out[key] = [_ordered_entry(p) for p in value]
        elif key == "defs":
            # Recursively, because a def can hold children that hold children.
            # Sorting only the def NAMES would leave the bodies in whatever
            # order they were typed, and `dumps(loads(t)) == t` would hold for
            # flat manifests and quietly fail for nested ones.
            out[key] = {name: _ordered_entry(value[name]) for name in sorted(value)}
        elif isinstance(value, dict):
            out[key] = dict(sorted(value.items()))
        else:
            out[key] = value
    return out


def _ordered_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """One part, ref, group or def — keys sorted, children ordered the same way."""
    out = dict(sorted(entry.items()))
    if isinstance(out.get("children"), list):
        out["children"] = [_ordered_entry(child) for child in out["children"]]
    return out


def dumps(manifest: Dict[str, Any]) -> str:
    """Byte-stable JSON: fixed key order, fixed separators, trailing newline.

    Stability is not tidiness. `dumps(loads(t)) == t` only holds for a stable
    writer, and without it every export of an unchanged scene shows a diff —
    which hides the one change you actually made.
    """
    return json.dumps(_ordered(validate(manifest)), indent=2,
                      separators=(",", ": "), allow_nan=False) + "\n"


def from_scene(scene: Dict[str, Any], provenance: Dict[str, Any] | None = None
               ) -> Dict[str, Any]:
    """A model's raw scene dict -> a versioned manifest that is VALID.

    The model's own output carries no version — the schema does not ask for one
    — so it is stamped here, which is the only place that knows it.

    AND THE PARTS ARE NORMALISED, which is the half that was missing. This
    stored the model's RAW values while the builder CLAMPED them, so a
    sculpture that rendered perfectly could produce a manifest the importer
    refused — a flame at `emissive_strength: 3.0`, a polished lighter at
    `roughness: 0.02`, a colour written without its `#`. Every consumer of the
    store then failed at once: the texture switch fell back to the untextured
    render under a note claiming it had draped, and both downloads returned
    `no_update`, which reads as a button that does nothing.

    `sculptor.normalise_part` is the single place the clamps live, and the
    builder reads its numbers from there too, so what is stored is exactly
    what was drawn.
    """
    parts, _notes = sculptor.normalise_scene(scene)
    out: Dict[str, Any] = {"version": FLAT_VERSION, "parts": parts}
    for field in ("name", "notes"):
        if scene.get(field):
            out[field] = str(scene[field])
    if provenance:
        out["provenance"] = {k: v for k, v in provenance.items()
                             if k in PROVENANCE_FIELDS and v is not None}
    return out


def render(manifest: Dict[str, Any],
           texture_png: Optional[bytes] = None) -> Tuple[bytes, List[str], int]:
    """Validate, then build. `provenance` is not passed on — nothing reads it.

    `texture_png` is a RENDER option, not part of the scene: the manifest stays
    textureless by design, so its bytes are identical whether or not it was ever
    draped, and an untextured `.glb` built today matches one built before the
    feature existed. See lib/texture.py.
    """
    return sculptor.build_placements(expand(manifest), texture_png=texture_png)


def filename(manifest: Dict[str, Any], extension: str) -> str:
    """A safe download name DERIVED from `name` — never the raw string.

    `name` comes from a model or from a visitor's edit, and it ends up in a
    Content-Disposition header. So it is slugged, length-capped, and given a
    fixed extension: `"../../etc/passwd"` becomes `etc-passwd.glb`, and a
    400-character name is truncated rather than passed on.
    """
    stem = _SLUG.sub("-", str(manifest.get("name") or "sculpture").lower()).strip("-")
    stem = stem[:48].strip("-") or "sculpture"
    return f"{stem}.{extension.lstrip('.')}"
