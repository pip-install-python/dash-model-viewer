"""Natural language → a validated `<model-viewer>` scene.

The demo that could not exist before 1.0.0. It needs the component to report
what it is looking at (`model_info`, `camera`) and to accept a scene back as
props — and 0.0.1 had no output props at all.

THE SHAPE
---------
    model_info + camera  ──►  grounded prompt  ──►  Claude (structured output)
                                                          │
                          props  ◄──  clamp + sanitise  ◄──┘

Two steps in that chain do the real work, and neither is the API call:

**Grounding.** The prompt carries the model's *measured* bounding box in
metres. Without it the model invents a camera radius in the wrong units and the
camera ends up inside the mesh or a kilometre away — and it does so
confidently, because "2.5m" is a perfectly plausible string.

**Clamping.** Structured output guarantees the *shape* of the JSON, never the
sanity of the numbers. Everything is re-checked against the geometry here.

No key configured is not an error state to paper over: `generate()` returns a
`SceneResult` with `ok=False` and a reason. The page renders and explains
itself; nothing pretends to have worked.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Claude Opus 5 — the task is spatial reasoning over a bounding box, which is
# exactly where a weaker model returns plausible JSON containing a camera
# inside the mesh. Effort is dialled down instead: the reasoning is short, and
# `low` keeps a docs-site demo from costing more than it needs to.
MODEL = "claude-opus-5"
MAX_TOKENS = 1500
EFFORT = "low"

# Attributes the model is NOT allowed to set, whatever it returns.
#
# Everything else is deliberately open — that is the whole point of the
# `attributes` escape hatch. But these fetch a resource, and model output must
# never be able to choose what the browser loads. `src` would let a prompt
# swap the model entirely; `ios-src`, `poster` and `environment-image` would
# let it point a user's browser at an arbitrary URL.
BLOCKED_ATTRIBUTES = frozenset(
    {"src", "ios-src", "poster", "environment-image", "skybox-image"}
)

# `environment-image` is genuinely useful for lighting, so it is offered as a
# curated choice rather than a free URL field.
ENVIRONMENT_PRESETS = {
    "neutral": "neutral",
    "legacy": "legacy",
}

TONE_MAPPINGS = ("neutral", "aces", "agx", "commerce")

_ORBIT = re.compile(
    r"^\s*(-?[\d.]+)deg\s+(-?[\d.]+)deg\s+([\d.]+)(m|cm|mm)?\s*$", re.I
)
_TARGET = re.compile(
    r"^\s*(-?[\d.]+)(m|cm|mm)?\s+(-?[\d.]+)(m|cm|mm)?\s+(-?[\d.]+)(m|cm|mm)?\s*$", re.I
)


@dataclass
class SceneResult:
    ok: bool
    reason: str = ""
    props: Dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    adjustments: List[str] = field(default_factory=list)


def available() -> bool:
    """True when a key is configured. Read at call time, never cached."""
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


# --------------------------------------------------------------------------
# Grounding
# --------------------------------------------------------------------------


def _bounding_sphere(dimensions: Optional[dict]) -> Optional[float]:
    if not dimensions:
        return None
    try:
        x, y, z = float(dimensions["x"]), float(dimensions["y"]), float(dimensions["z"])
    except (KeyError, TypeError, ValueError):
        return None
    return max(x, y, z)


def _system_prompt(model_info: dict, camera: Optional[dict]) -> str:
    dims = (model_info or {}).get("dimensions") or {}
    variants = (model_info or {}).get("variants") or []
    span = _bounding_sphere(dims)

    lines = [
        "You are a 3D staging director for Google's <model-viewer> web component.",
        "Given a request in plain language, return a camera and lighting setup "
        "that realises it.",
        "",
        "THIS MODEL, measured (metres):",
    ]
    if dims:
        lines.append(
            f"  width(x)={dims.get('x'):.3f}  height(y)={dims.get('y'):.3f}  "
            f"depth(z)={dims.get('z'):.3f}"
        )
    else:
        lines.append("  (not yet reported — the model is still loading)")

    lines += [
        f"  available material variants: {variants or 'none'}",
        "",
        "CURRENT CAMERA:",
        f"  orbit={(camera or {}).get('orbit', 'unset')}  "
        f"target={(camera or {}).get('target', 'unset')}  "
        f"fov={(camera or {}).get('field_of_view', 'unset')}",
        "",
        "RULES — these are geometry, not style:",
        "- camera_orbit is 'THETAdeg PHIdeg RADIUSm'. theta is azimuth; phi is "
        "measured from +Y, so 0deg is directly overhead and 90deg is level.",
        "- Keep phi between 10deg and 170deg. At 0 or 180 the camera is on the "
        "pole and the view rolls unpredictably.",
    ]
    if span:
        lines.append(
            f"- Keep radius between {span * 0.8:.2f}m and {span * 3.0:.2f}m. "
            f"Below that the camera is inside the mesh."
        )
        lines.append(
            f"- camera_target should sit inside the model: y between 0 and "
            f"{dims.get('y', 1):.2f}."
        )
    lines += [
        "- Only use a variant_name from the list above, or null.",
        f"- tone_mapping must be one of: {', '.join(TONE_MAPPINGS)}.",
        "",
        "The `attributes` field takes any other model-viewer attribute in "
        "kebab-case — exposure, auto-rotate, orientation, shadow-softness, "
        "auto-rotate-delay, rotation-per-second, camera-orbit is NOT allowed "
        "there (use the named field).",
        "Do not set src, poster, environment-image, skybox-image or ios-src.",
        "",
        "Keep `rationale` to one sentence, addressed to the person who asked.",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Clamping — structured output guarantees shape, never sanity
# --------------------------------------------------------------------------


def _clamp(scene: dict, model_info: dict) -> tuple[dict, List[str]]:
    notes: List[str] = []
    dims = (model_info or {}).get("dimensions") or {}
    span = _bounding_sphere(dims)

    orbit = scene.get("camera_orbit") or ""
    match = _ORBIT.match(orbit)
    if match:
        theta, phi, radius = float(match[1]), float(match[2]), float(match[3])
        unit = (match[4] or "m").lower()
        radius *= {"m": 1.0, "cm": 0.01, "mm": 0.001}[unit]

        if not 10 <= phi <= 170:
            phi = min(170.0, max(10.0, phi))
            notes.append(f"phi clamped to {phi:g}deg (pole roll)")
        if span:
            lo, hi = span * 0.8, span * 3.0
            if not lo <= radius <= hi:
                radius = min(hi, max(lo, radius))
                notes.append(f"radius clamped to {radius:.2f}m for this model")
        scene["camera_orbit"] = f"{theta:g}deg {phi:g}deg {radius:.2f}m"
    elif orbit:
        notes.append(f"discarded unparseable camera_orbit {orbit!r}")
        scene.pop("camera_orbit", None)

    target = scene.get("camera_target") or ""
    if target and not _TARGET.match(target):
        notes.append(f"discarded unparseable camera_target {target!r}")
        scene.pop("camera_target", None)

    variants = (model_info or {}).get("variants") or []
    name = scene.get("variant_name")
    if name and name not in variants:
        notes.append(f"variant {name!r} is not in this model; using the default")
        scene["variant_name"] = None

    if scene.get("tone_mapping") not in TONE_MAPPINGS:
        scene.pop("tone_mapping", None)

    intensity = scene.get("shadow_intensity")
    if isinstance(intensity, (int, float)):
        scene["shadow_intensity"] = min(1.0, max(0.0, float(intensity)))
    else:
        scene.pop("shadow_intensity", None)

    # The model returns a list of {name, value} pairs (see _schema); fold it
    # back into the dict the `attributes` prop takes. A dict is still accepted
    # so the clamping stays unit-testable without going through the API.
    raw = scene.get("attributes") or []
    if isinstance(raw, dict):
        pairs = list(raw.items())
    else:
        pairs = [
            (item.get("name"), item.get("value"))
            for item in raw
            if isinstance(item, dict) and item.get("name")
        ]

    safe = {}
    for key, value in pairs:
        key = str(key).strip().lower()
        if key in BLOCKED_ATTRIBUTES:
            notes.append(f"blocked attribute {key!r} (model output may not fetch)")
            continue
        if key.replace("-", "_") in {"camera_orbit", "camera_target", "field_of_view"}:
            continue  # named props own these
        safe[key] = str(value)
    scene["attributes"] = safe

    return scene, notes


# --------------------------------------------------------------------------
# The call
# --------------------------------------------------------------------------


def _schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "camera_orbit": {
                "type": "string",
                "description": "'THETAdeg PHIdeg RADIUSm', e.g. '45deg 70deg 2.5m'",
            },
            "camera_target": {
                "type": "string",
                "description": "'X Y Z' in metres, e.g. '0m 0.9m 0m'",
            },
            "field_of_view": {"type": "string", "description": "e.g. '32deg'"},
            "tone_mapping": {"type": "string", "enum": list(TONE_MAPPINGS)},
            "shadow_intensity": {"type": "number"},
            "variant_name": {"type": ["string", "null"]},
            # A LIST OF PAIRS, not a dict.
            #
            # Structured outputs require `additionalProperties: false` on every
            # object, which makes a free-form map inexpressible — the API
            # rejects `additionalProperties: {"type": "string"}` outright. An
            # open-ended key space therefore has to be modelled as a list of
            # {name, value} pairs and folded back into a dict afterwards.
            # Enumerating the allowed names instead would throw away the whole
            # point of the parity hatch.
            "attributes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "kebab-case model-viewer attribute",
                        },
                        "value": {"type": "string"},
                    },
                    "required": ["name", "value"],
                    "additionalProperties": False,
                },
                "description": "Any other model-viewer attributes, as pairs.",
            },
            "rationale": {"type": "string"},
        },
        "required": [
            "camera_orbit",
            "camera_target",
            "field_of_view",
            "tone_mapping",
            "shadow_intensity",
            "variant_name",
            "attributes",
            "rationale",
        ],
        "additionalProperties": False,
    }


def generate(
    request: str,
    model_info: Optional[dict] = None,
    camera: Optional[dict] = None,
) -> SceneResult:
    """Turn a plain-language request into clamped `ModelViewer` props."""
    request = (request or "").strip()
    if not request:
        return SceneResult(ok=False, reason="Describe the shot you want.")
    if len(request) > 500:
        return SceneResult(ok=False, reason="Keep the request under 500 characters.")

    if not available():
        return SceneResult(
            ok=False,
            reason=(
                "ANTHROPIC_API_KEY is not set on this host, so the director is "
                "off. Everything else on this page — the grounding, the schema "
                "and the clamping — is in lib/scene_director.py and needs no key "
                "to read."
            ),
        )

    if not (model_info or {}).get("dimensions"):
        return SceneResult(
            ok=False,
            reason="The model has not reported its dimensions yet — try again in a moment.",
        )

    try:
        import anthropic
    except ImportError:
        return SceneResult(ok=False, reason="The `anthropic` package is not installed.")

    import json

    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=_system_prompt(model_info or {}, camera),
            output_config={
                "effort": EFFORT,
                "format": {"type": "json_schema", "schema": _schema()},
            },
            messages=[{"role": "user", "content": request}],
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the page, not swallowed
        return SceneResult(ok=False, reason=f"{type(exc).__name__}: {exc}")

    # Always before reading content: a safety decline returns HTTP 200 with an
    # empty content list, and indexing content[0] would raise instead of
    # explaining.
    if response.stop_reason == "refusal":
        return SceneResult(
            ok=False, reason="The request was declined by the model's safety system."
        )

    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        scene = json.loads(text)
    except ValueError:
        return SceneResult(ok=False, reason="The model did not return usable JSON.")

    rationale = str(scene.pop("rationale", "")).strip()
    scene, notes = _clamp(scene, model_info or {})

    props = {k: v for k, v in scene.items() if v is not None or k == "variant_name"}
    return SceneResult(ok=True, props=props, rationale=rationale, adjustments=notes)
