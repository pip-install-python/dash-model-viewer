# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
import numbers # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component
try:
    from dash.development.base_component import ComponentType # noqa: F401
except ImportError:
    ComponentType = typing.TypeVar("ComponentType", bound=Component)


class DashModelViewer(Component):
    """A DashModelViewer component.


Keyword arguments:

- id (string; required):
    Component ID.

- alt (string; required):
    Alt text for accessibility.

- ar (boolean; default True):
    Enable AR features.

- arButtonText (string; default 'View in your space'):
    Text for the default AR button.

- arModes (string; default "basic_annotations scene-viewer quick-look")

- arScale (a value equal to: 'auto', 'fixed'; default 'auto')

- cameraControls (boolean; default True):
    Enable camera controls.

- cameraOrbit (string; optional):
    Initial camera orbital position ($theta $phi $radius).

- cameraTarget (string; optional):
    Initial camera target point ($X $Y $Z).

- customArFailure (string | a list of or a singular dash component, string or number; optional):
    Custom React element for the AR failure message.

- customArPrompt (string | a list of or a singular dash component, string or number; optional):
    Custom React element for the AR prompt.

- fieldOfView (string; default 'auto'):
    Camera field of view.

- hotspots (list of dicts; optional):
    Array of hotspot objects passed from the server.

    `hotspots` is a list of dicts with keys:

    - slot (string; optional)

    - position (string; optional)

    - normal (string; optional)

    - orbit (string; optional)

    - target (string; optional)

    - fov (string; optional)

    - text (string; optional)

    - children_classname (string; optional)

- interpolationDecay (number | string; default 50):
    Camera interpolation decay rate.

- loading_state (dict; optional):
    Object that holds the loading state object coming from
    dash-renderer.

    `loading_state` is a dict with keys:

    - is_loading (boolean; optional):
        Determines if the component is loading or not.

    - prop_name (string; optional):
        Holds which property is loading.

    - component_name (string; optional):
        Holds the name of the component that is loading.

- maxCameraOrbit (string; default 'auto auto auto'):
    Maximum camera orbit bounds.

- maxFieldOfView (string; default 'auto'):
    Maximum camera field of view.

- minCameraOrbit (string; default 'auto auto auto'):
    Minimum camera orbit bounds.

- minFieldOfView (string; default '25deg'):
    Minimum camera field of view.

- poster (string; optional):
    Poster image URL.

- shadowIntensity (number | string; default 0)

- src (string; required):
    Model source URL (.glb or .gltf).

- toneMapping (a value equal to: 'neutral', 'aces', 'agx', 'reinhard', 'cineon', 'linear', 'none'; default 'neutral')

- touchAction (a value equal to: 'pan-y', 'pan-x', 'none'; default "pan-y"):
    Touch action behavior.

- variantName (string; optional)"""
    _children_props = ['customArPrompt', 'customArFailure']
    _base_nodes = ['customArPrompt', 'customArFailure', 'children']
    _namespace = 'dash_model_viewer'
    _type = 'DashModelViewer'
    Hotspots = TypedDict(
        "Hotspots",
            {
            "slot": NotRequired[str],
            "position": NotRequired[str],
            "normal": NotRequired[str],
            "orbit": NotRequired[str],
            "target": NotRequired[str],
            "fov": NotRequired[str],
            "text": NotRequired[str],
            "children_classname": NotRequired[str]
        }
    )

    LoadingState = TypedDict(
        "LoadingState",
            {
            "is_loading": NotRequired[bool],
            "prop_name": NotRequired[str],
            "component_name": NotRequired[str]
        }
    )

    _explicitize_dash_init = True

    def __init__(
        self,
        id: typing.Optional[typing.Union[str, dict]] = None,
        src: typing.Optional[str] = None,
        alt: typing.Optional[str] = None,
        cameraControls: typing.Optional[bool] = None,
        touchAction: typing.Optional[Literal["pan-y", "pan-x", "none"]] = None,
        cameraOrbit: typing.Optional[str] = None,
        cameraTarget: typing.Optional[str] = None,
        fieldOfView: typing.Optional[str] = None,
        minFieldOfView: typing.Optional[str] = None,
        maxFieldOfView: typing.Optional[str] = None,
        interpolationDecay: typing.Optional[typing.Union[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex], str]] = None,
        minCameraOrbit: typing.Optional[str] = None,
        maxCameraOrbit: typing.Optional[str] = None,
        poster: typing.Optional[str] = None,
        ar: typing.Optional[bool] = None,
        hotspots: typing.Optional[typing.Sequence["Hotspots"]] = None,
        arButtonText: typing.Optional[str] = None,
        customArPrompt: typing.Optional[typing.Union[str, typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]]] = None,
        customArFailure: typing.Optional[typing.Union[str, typing.Union[str, int, float, ComponentType, typing.Sequence[typing.Union[str, int, float, ComponentType]]]]] = None,
        style: typing.Optional[typing.Any] = None,
        toneMapping: typing.Optional[Literal["neutral", "aces", "agx", "reinhard", "cineon", "linear", "none"]] = None,
        arModes: typing.Optional[str] = None,
        shadowIntensity: typing.Optional[typing.Union[typing.Union[typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex], str]] = None,
        arScale: typing.Optional[Literal["auto", "fixed"]] = None,
        variantName: typing.Optional[str] = None,
        loading_state: typing.Optional["LoadingState"] = None,
        **kwargs
    ):
        self._prop_names = ['id', 'alt', 'ar', 'arButtonText', 'arModes', 'arScale', 'cameraControls', 'cameraOrbit', 'cameraTarget', 'customArFailure', 'customArPrompt', 'fieldOfView', 'hotspots', 'interpolationDecay', 'loading_state', 'maxCameraOrbit', 'maxFieldOfView', 'minCameraOrbit', 'minFieldOfView', 'poster', 'shadowIntensity', 'src', 'style', 'toneMapping', 'touchAction', 'variantName']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['id', 'alt', 'ar', 'arButtonText', 'arModes', 'arScale', 'cameraControls', 'cameraOrbit', 'cameraTarget', 'customArFailure', 'customArPrompt', 'fieldOfView', 'hotspots', 'interpolationDecay', 'loading_state', 'maxCameraOrbit', 'maxFieldOfView', 'minCameraOrbit', 'minFieldOfView', 'poster', 'shadowIntensity', 'src', 'style', 'toneMapping', 'touchAction', 'variantName']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        for k in ['id', 'alt', 'src']:
            if k not in args:
                raise TypeError(
                    'Required argument `' + k + '` was not specified.')

        super(DashModelViewer, self).__init__(**args)
