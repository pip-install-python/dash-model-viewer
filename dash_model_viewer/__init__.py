"""dash-model-viewer — interactive 3D models and AR for Dash.

Embed Google's ``<model-viewer>`` in a Dash application, with real Dash props
in both directions and Augmented Reality that works out of the box.

    import dash_model_viewer as dmv

    dmv.ModelViewer(
        id="viewer",
        src="/assets/astronaut.glb",
        alt="A 3D model of an astronaut",
        style={"width": "100%", "height": "480px"},
    )

Importing this package is enough to install the runtime — the vendored
``model-viewer`` bundle is emitted through a Dash hook, so you do not need to
add anything to ``external_scripts`` and no request leaves your server.
"""

from __future__ import annotations

import typing
import warnings

from dash import hooks

from ._components import (  # noqa: F401
    DEFAULT_AR_MODES,
    DEFAULT_CAMERA_CHANGE_DEBOUNCE,
    ModelViewer,
    Slot,
)

__all__ = [
    "ModelViewer",
    "Slot",
    "configure",
    "DEFAULT_AR_MODES",
    "DEFAULT_CAMERA_CHANGE_DEBOUNCE",
    "MODEL_VIEWER_VERSION",
    "__version__",
]

_PACKAGE_NAME = "dash-model-viewer"
_NAMESPACE = "dash_model_viewer"

# Version comes from installed metadata, never from a JSON file in the package.
# A `package-info.json` read at import time is one of the artefacts the
# anti-regeneration test forbids; it is also how 0.0.1 ended up able to
# regenerate itself backwards from a stale dev environment.
try:  # pragma: no cover - trivial
    from importlib.metadata import PackageNotFoundError, version as _version

    __version__ = _version(_PACKAGE_NAME)
except PackageNotFoundError:  # pragma: no cover - source checkout, not installed
    __version__ = "0.0.0.dev0"

# CDN mirror, used only when configure(use_cdn=...) asks for it.
_CDN_TEMPLATE = "https://cdn.jsdelivr.net/npm/@google/model-viewer@{v}/dist/model-viewer-umd.min.js"
MODEL_VIEWER_VERSION = "4.3.1"

# These dicts are registered with Dash once, below, and mutated in place by
# configure(). `hooks.script()` extends a list with these *references*, so an
# in-place edit is visible to Dash; rebinding the names would not be.
#
# NOTE: no "type" attribute and no "async" key, deliberately. Either one defers
# execution past `new DashRenderer(...)` and reintroduces the custom-element
# race this architecture exists to remove. tests/test_hook.py asserts both.
_VENDOR_RESOURCE: typing.Dict[str, typing.Any] = {
    "namespace": _NAMESPACE,
    "relative_package_path": "vendor/model-viewer-umd.min.js",
}

_SHIM_RESOURCE: typing.Dict[str, typing.Any] = {
    "namespace": _NAMESPACE,
    "relative_package_path": "dash_model_viewer.js",
}

# Order matters: the custom element must be defined before the shim's rendered
# output reaches the DOM.
hooks.script([_VENDOR_RESOURCE, _SHIM_RESOURCE])

_configured = False


def configure(use_cdn: typing.Union[bool, str] = False) -> None:
    """Serve the ``model-viewer`` bundle from somewhere other than this wheel.

    By default the bundle ships inside the package and is served by your own
    Dash server. That is the point of the vendoring: no CDN dependency, works
    offline, works behind an egress proxy, works under a strict ``script-src``
    Content-Security-Policy, and the version is pinned by your lockfile.

    Call this only if you need the opposite:

        import dash_model_viewer as dmv

        dmv.configure(use_cdn=True)                       # public jsDelivr
        dmv.configure(use_cdn="https://cdn.example/mv.js") # internal mirror

        app = Dash(__name__)

    **This must run before the first request is served.** Dash reads the hook
    resource list while generating the index page, so a call made from inside a
    callback or a lazily-imported page module may or may not take effect
    depending on which request arrives first — which is worse than never
    working. Put the call at module scope, next to the import.

    Args:
        use_cdn: ``False`` (default) to serve the vendored bundle,
            ``True`` for the public jsDelivr copy of the pinned version, or a
            URL string for your own mirror.
    """
    global _configured  # pylint: disable=global-statement

    if _configured:
        warnings.warn(
            "dash_model_viewer.configure() called more than once; the last "
            "call wins, and only if it ran before the first request was served.",
            RuntimeWarning,
            stacklevel=2,
        )
    _configured = True

    if not use_cdn:
        _VENDOR_RESOURCE.pop("external_url", None)
        _VENDOR_RESOURCE.pop("external_only", None)
        _VENDOR_RESOURCE["relative_package_path"] = "vendor/model-viewer-umd.min.js"
        return

    url = (
        _CDN_TEMPLATE.format(v=MODEL_VIEWER_VERSION)
        if use_cdn is True
        else str(use_cdn)
    )
    # Keep relative_package_path as the fallback; external_only is what makes
    # Dash prefer the URL even with serve_locally=True.
    _VENDOR_RESOURCE["external_url"] = url
    _VENDOR_RESOURCE["external_only"] = True
