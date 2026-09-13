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

from lib import sculptor

#: The only version this build reads or writes.
VERSION = 1

#: Cap on an imported manifest, in bytes of JSON. A manifest for the maximum
#: 28 parts is roughly 8 KB, so this is generous by a wide margin and exists to
#: bound the parse, not to be reached.
MAX_JSON_BYTES = 256 * 1024

TOP_LEVEL = {"version", "parts", "name", "notes", "provenance"}
REQUIRED_TOP = {"version", "parts"}

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


def _part(part: Any, index: int) -> None:
    where = f"parts[{index}]"
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
    if version != VERSION:
        raise ManifestError(
            f"version: this manifest is version {version}; this build reads "
            f"version {VERSION}. It is not read partially — a newer manifest "
            f"may use shapes this build cannot render."
        )

    unknown = set(manifest) - TOP_LEVEL
    if unknown:
        raise ManifestError(f"{sorted(unknown)[0]}: unknown key")
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
    if len(parts) > sculptor.MAX_PARTS:
        raise ManifestError(
            f"parts: {len(parts)} parts, and the limit is {sculptor.MAX_PARTS}"
        )
    for index, part in enumerate(parts):
        _part(part, index)
    return manifest


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
            out[key] = [dict(sorted(p.items())) for p in value]
        elif isinstance(value, dict):
            out[key] = dict(sorted(value.items()))
        else:
            out[key] = value
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
    """A model's raw scene dict -> a versioned manifest.

    The model's own output carries no version — the schema does not ask for one
    — so it is stamped here, which is the only place that knows it.
    """
    out: Dict[str, Any] = {"version": VERSION, "parts": scene.get("parts") or []}
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
    validated = validate(manifest)
    scene = {k: v for k, v in validated.items()
             if k not in ("version", "provenance")}
    return sculptor.build(scene, texture_png=texture_png)


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
