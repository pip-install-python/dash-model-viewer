"""Hand-written Dash components for ``<model-viewer>``.

HAND-AUTHORED. This module is deliberately *not* generated — there is no
``dash-generate-components`` step, no ``metadata.json`` and no React source in
this package. See ``.claude/ARCHITECTURE.md``.

The filename ``DashModelViewer.py`` is retired on purpose: a stale copy left
over from the 0.0.1 build cannot shadow anything here.
"""

from __future__ import annotations

import typing

from dash.development.base_component import Component

__all__ = ["ModelViewer", "Slot"]

ComponentSingleType = typing.Union[str, int, float, Component, None]
ComponentType = typing.Union[
    ComponentSingleType, typing.Sequence[ComponentSingleType]
]

NAMESPACE = "dash_model_viewer"

#: The AR modes model-viewer actually understands.
#:
#: 0.0.1 shipped ``"basic_annotations scene-viewer quick-look"``. There is no
#: such AR mode as ``basic_annotations`` — it is the name of a folder in
#: ``usage_tests/``. Because ``webxr`` was therefore absent from the default,
#: WebXR AR was silently off on Android in every default configuration.
DEFAULT_AR_MODES = "webxr scene-viewer quick-look"

#: Milliseconds. ``camera-change`` fires at frame rate; see ModelViewer docs.
DEFAULT_CAMERA_CHANGE_DEBOUNCE = 100


class ModelViewer(Component):
    """An interactive 3D model with Augmented Reality support.

    Wraps Google's ``<model-viewer>`` web component. The bundle is vendored
    inside this package and injected by a Dash hook at import time, so no
    network access is required at runtime.

    Three prop families, in increasing order of escape-hatch-ness:

    1. **Named props** — the common attributes, validated and documented.
    2. **``mv_*`` wildcards** — ``mv_environment_image="neutral"`` sets the
       ``environment-image`` attribute.
    3. **``attributes`` dict** — ``{"environment-image": "neutral"}``.

    Families 2 and 3 reach every attribute model-viewer supports, including
    ones added upstream after this release. Precedence when the same attribute
    is set more than once: **named > ``mv_*`` > ``attributes``**.

    Keyword arguments:

    - children (list of components; optional):
        ``Slot`` components. Hotspots, a custom AR button, a poster, a
        progress bar — every one of those is a named slot.

    - id (string | dict; optional):
        Component id for callbacks.

    - src (string; required):
        URL of the ``.glb`` / ``.gltf`` model.

    - alt (string; required):
        Accessible description of the model. Required, and not decorative:
        it is the only thing a screen-reader user gets.

    - style (dict; optional):
        CSS for the viewer element. It has no intrinsic size — give it one.

    - class_name (string; optional):
        CSS class for the viewer element.

    - camera_controls (boolean; default True):
        Let the user orbit, zoom and pan.

    - touch_action ('pan-y' | 'pan-x' | 'none'; default 'pan-y'):
        Which touch gestures the page keeps rather than the model.

    - camera_orbit (string; optional):
        ``"theta phi radius"``, e.g. ``"45deg 70deg 2.5m"``. Two-way: also
        reported back through ``camera``.

    - camera_target (string; optional):
        ``"X Y Z"`` in metres, e.g. ``"0m 1m 0m"``.

    - field_of_view (string; optional):
        e.g. ``"30deg"``.

    - min_field_of_view / max_field_of_view (string; optional):
        Zoom limits.

    - min_camera_orbit / max_camera_orbit (string; optional):
        Orbit limits, ``"auto auto auto"`` for none.

    - interpolation_decay (number; optional):
        Camera transition speed. Lower is slower; ``0`` is instant. This is
        what makes a programmatic camera move read as a flight rather than a
        jump-cut.

    - poster (string; optional):
        Image shown until the model is ready.

    - ar (boolean; default True):
        Enable AR and show the AR affordance where supported.

    - ar_modes (string; default "webxr scene-viewer quick-look"):
        Space-separated AR back-ends, most preferred first.

    - ar_scale ('auto' | 'fixed'; default 'auto'):
        Whether AR may rescale the model.

    - tone_mapping (string; default 'neutral'):
        ``neutral``, ``aces``, ``agx``, ``commerce``, ...

    - shadow_intensity (number; optional):
        0 to 1.

    - variant_name (string; optional):
        GLTF material variant. ``None`` (or ``"default"``) selects the
        model's default.

    - camera_change_debounce (number; default 100):
        Milliseconds to coalesce ``camera-change`` events before updating
        ``camera``. **Do not set this to 0 casually** — the event fires at
        frame rate, so 0 means a callback per frame per viewer.

    - pick_on_click (boolean; default False):
        When True, clicking the model reports the 3D surface point under the
        cursor through ``scene_point``.

    - attributes (dict; optional):
        Raw kebab-case model-viewer attributes.

    Read-only props, updated by the component:

    - camera (dict):
        ``{"orbit", "target", "field_of_view", "source"}``. Only user
        interaction is reported — programmatic changes are suppressed, or a
        callback that writes ``camera_orbit`` would re-trigger itself.

    - model_state (dict):
        ``{"status": "loading" | "loaded" | "error", "progress": float}``.

    - model_info (dict):
        ``{"dimensions": {"x","y","z"}, "variants": [...],
        "animations": [...]}``, set on load. Dimensions are in metres — this
        is the prop that removes the bounding-box maths from user JS.

    - ar_status (string):
        ``session-started``, ``object-placed``, ``failed``, ...

    - ar_tracking (string):
        ``tracking`` or ``not-tracking``.

    - scene_point (dict):
        ``{"position", "normal", "uv"}`` for the last picked point, when
        ``pick_on_click`` is set.
    """

    _namespace = NAMESPACE
    _type = "ModelViewer"
    _children_props: typing.List[str] = []
    _base_nodes = ["children"]

    _prop_names = [
        "children",
        "id",
        "src",
        "alt",
        "style",
        "class_name",
        "camera_controls",
        "touch_action",
        "camera_orbit",
        "camera_target",
        "field_of_view",
        "min_field_of_view",
        "max_field_of_view",
        "min_camera_orbit",
        "max_camera_orbit",
        "interpolation_decay",
        "poster",
        "ar",
        "ar_modes",
        "ar_scale",
        "tone_mapping",
        "shadow_intensity",
        "variant_name",
        "camera_change_debounce",
        "pick_on_click",
        "attributes",
        "camera",
        "model_state",
        "model_info",
        "ar_status",
        "ar_tracking",
        "scene_point",
    ]
    available_properties = _prop_names

    _valid_wildcard_attributes = ["mv_"]
    available_wildcard_properties = ["mv_"]

    # pylint: disable=too-many-locals,redefined-builtin
    def __init__(
        self,
        children: typing.Optional[ComponentType] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        src: typing.Optional[str] = None,
        alt: typing.Optional[str] = None,
        style: typing.Optional[dict] = None,
        class_name: typing.Optional[str] = None,
        camera_controls: bool = True,
        touch_action: str = "pan-y",
        camera_orbit: typing.Optional[str] = None,
        camera_target: typing.Optional[str] = None,
        field_of_view: typing.Optional[str] = None,
        min_field_of_view: typing.Optional[str] = None,
        max_field_of_view: typing.Optional[str] = None,
        min_camera_orbit: typing.Optional[str] = None,
        max_camera_orbit: typing.Optional[str] = None,
        interpolation_decay: typing.Optional[float] = None,
        poster: typing.Optional[str] = None,
        ar: bool = True,
        ar_modes: str = DEFAULT_AR_MODES,
        ar_scale: str = "auto",
        tone_mapping: str = "neutral",
        shadow_intensity: typing.Optional[float] = None,
        variant_name: typing.Optional[str] = None,
        camera_change_debounce: float = DEFAULT_CAMERA_CHANGE_DEBOUNCE,
        pick_on_click: bool = False,
        attributes: typing.Optional[typing.Dict[str, str]] = None,
        camera: typing.Optional[dict] = None,
        model_state: typing.Optional[dict] = None,
        model_info: typing.Optional[dict] = None,
        ar_status: typing.Optional[str] = None,
        ar_tracking: typing.Optional[str] = None,
        scene_point: typing.Optional[dict] = None,
        **kwargs,
    ):
        args = {
            "id": id,
            "src": src,
            "alt": alt,
            "style": style,
            "class_name": class_name,
            "camera_controls": camera_controls,
            "touch_action": touch_action,
            "camera_orbit": camera_orbit,
            "camera_target": camera_target,
            "field_of_view": field_of_view,
            "min_field_of_view": min_field_of_view,
            "max_field_of_view": max_field_of_view,
            "min_camera_orbit": min_camera_orbit,
            "max_camera_orbit": max_camera_orbit,
            "interpolation_decay": interpolation_decay,
            "poster": poster,
            "ar": ar,
            "ar_modes": ar_modes,
            "ar_scale": ar_scale,
            "tone_mapping": tone_mapping,
            "shadow_intensity": shadow_intensity,
            "variant_name": variant_name,
            "camera_change_debounce": camera_change_debounce,
            "pick_on_click": pick_on_click,
            "attributes": attributes,
            "camera": camera,
            "model_state": model_state,
            "model_info": model_info,
            "ar_status": ar_status,
            "ar_tracking": ar_tracking,
            "scene_point": scene_point,
        }
        args = {k: v for k, v in args.items() if v is not None}
        args.update(kwargs)
        super().__init__(children=children, **args)


class Slot(Component):
    """A named slot inside a :class:`ModelViewer`.

    ``<model-viewer>`` places its extras — hotspots, the AR button, the AR
    prompt, the poster, the progress bar — into named shadow-DOM slots. Plain
    ``dash.html.Div`` has no ``slot`` prop, which is the entire reason 0.0.1
    expressed hotspots as a list of dictionaries and could not put arbitrary
    Dash components inside them.

    A hotspot is a slot whose name starts with ``hotspot-`` and which carries a
    ``position``:

        Slot(slot="hotspot-sole", position="0 0.1 0.2", normal="0 1 0",
             children=dmc.Badge("Sole"))

    Any other slot name is passed through, so the AR button is just:

        Slot(slot="ar-button", children=html.Button("View in your space"))

    Keyword arguments:

    - children (list of components; optional):
        Slot content. Any Dash component.

    - id (string | dict; optional):
        Component id for callbacks.

    - slot (string; required):
        The slot name, e.g. ``"hotspot-1"``, ``"ar-button"``, ``"poster"``.

    - position (string; optional):
        ``"X Y Z"`` in model space. Required for hotspots.

    - normal (string; optional):
        ``"X Y Z"`` surface normal; controls hotspot occlusion behaviour.

    - style (dict; optional):
        CSS for the slot element.

    - class_name (string; optional):
        Added alongside the built-in ``dmv-slot`` class.

    - n_clicks (number; default 0):
        Increments on click. Use as a callback ``Input`` — this is how a
        hotspot drives a camera move without any clientside JavaScript.
    """

    _namespace = NAMESPACE
    _type = "Slot"
    _children_props: typing.List[str] = []
    _base_nodes = ["children"]

    _prop_names = [
        "children",
        "id",
        "slot",
        "position",
        "normal",
        "style",
        "class_name",
        "n_clicks",
    ]
    available_properties = _prop_names

    _valid_wildcard_attributes: typing.List[str] = []
    available_wildcard_properties: typing.List[str] = []

    # pylint: disable=redefined-builtin
    def __init__(
        self,
        children: typing.Optional[ComponentType] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        slot: typing.Optional[str] = None,
        position: typing.Optional[str] = None,
        normal: typing.Optional[str] = None,
        style: typing.Optional[dict] = None,
        class_name: typing.Optional[str] = None,
        n_clicks: int = 0,
        **kwargs,
    ):
        args = {
            "id": id,
            "slot": slot,
            "position": position,
            "normal": normal,
            "style": style,
            "class_name": class_name,
            "n_clicks": n_clicks,
        }
        args = {k: v for k, v in args.items() if v is not None}
        args.update(kwargs)
        super().__init__(children=children, **args)
