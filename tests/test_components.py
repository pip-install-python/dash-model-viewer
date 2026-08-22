"""API-surface tests: defaults, the hook resources, and the timing guards.

None of these need a browser. They are cheap, and every one of them covers a
defect that shipped in 0.0.1 without anybody noticing.
"""

from __future__ import annotations

import pathlib

import pytest

import dash_model_viewer as dmv

PKG = pathlib.Path(dmv.__file__).resolve().parent


# --------------------------------------------------------------------------
# The bug that justifies the major version
# --------------------------------------------------------------------------


def test_ar_modes_default_enables_webxr():
    """0.0.1 defaulted to "basic_annotations scene-viewer quick-look".

    `basic_annotations` is not an AR mode — it is a folder name in
    usage_tests/, copy-pasted into the default. Because `webxr` was missing,
    WebXR AR was silently off on Android in every default configuration.
    """
    viewer = dmv.ModelViewer(id="v", src="/m.glb", alt="a model")
    assert viewer.ar_modes == "webxr scene-viewer quick-look"
    assert "webxr" in viewer.ar_modes.split()
    assert "basic_annotations" not in viewer.ar_modes


def test_ar_modes_contains_only_real_modes():
    valid = {"webxr", "scene-viewer", "quick-look"}
    assert set(dmv.DEFAULT_AR_MODES.split()) <= valid


# --------------------------------------------------------------------------
# camera_change_debounce is mandatory, not decorative
# --------------------------------------------------------------------------


def test_camera_change_debounce_defaults_nonzero():
    """`camera-change` fires at frame rate; 0 is a callback per frame."""
    viewer = dmv.ModelViewer(id="v", src="/m.glb", alt="a model")
    assert viewer.camera_change_debounce == 100
    assert viewer.camera_change_debounce > 0


def test_camera_change_debounce_is_a_named_prop():
    assert "camera_change_debounce" in dmv.ModelViewer._prop_names


def test_shim_suppresses_programmatic_camera_events():
    """Without the source check, a callback writing camera_orbit loops."""
    shim = (PKG / "dash_model_viewer.js").read_text(encoding="utf-8")
    assert 'source !== "user-interaction"' in shim


# --------------------------------------------------------------------------
# Output props — the half of the component that never worked
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prop",
    ["camera", "model_state", "model_info", "ar_status", "ar_tracking", "scene_point"],
)
def test_output_props_exist(prop):
    assert prop in dmv.ModelViewer._prop_names


def test_shim_actually_calls_setprops():
    """0.0.1 had the only setProps call commented out."""
    shim = (PKG / "dash_model_viewer.js").read_text(encoding="utf-8")
    assert "// setProps(" not in shim
    assert "fn(update)" in shim


def test_shim_removes_the_listeners_it_added():
    """0.0.1 removed fresh closures, so listeners accumulated forever."""
    shim = (PKG / "dash_model_viewer.js").read_text(encoding="utf-8")
    added = shim.count("el.addEventListener(")
    removed = shim.count("el.removeEventListener(")
    assert added == removed, "every listener added on mount must be removed"


# --------------------------------------------------------------------------
# Script timing — silent failures, so they get explicit tests
# --------------------------------------------------------------------------


def test_vendor_resource_is_the_umd_build():
    """The ESM build is deferred past `new DashRenderer(...)`; UMD is not."""
    path = dmv._VENDOR_RESOURCE["relative_package_path"]
    assert path.endswith("-umd.min.js"), path


def test_hook_resources_are_classic_scripts():
    """`type=module` or any `async` reintroduces the custom-element race."""
    for resource in (dmv._VENDOR_RESOURCE, dmv._SHIM_RESOURCE):
        assert "async" not in resource, resource
        assert resource.get("attributes", {}).get("type") is None, resource


def test_hook_resources_are_registered_with_dash():
    from dash._hooks import HooksManager

    registered = HooksManager.hooks._js_dist
    assert dmv._VENDOR_RESOURCE in registered
    assert dmv._SHIM_RESOURCE in registered
    # Order matters: the custom element before the shim that renders it.
    assert registered.index(dmv._VENDOR_RESOURCE) < registered.index(
        dmv._SHIM_RESOURCE
    )


def test_vendored_bundle_is_present_and_real():
    bundle = PKG / "vendor" / "model-viewer-umd.min.js"
    assert bundle.is_file()
    # ~1 MB; a truncated or LFS-pointer file would be tiny.
    assert bundle.stat().st_size > 500_000, bundle.stat().st_size
    head = bundle.read_bytes()[:400].decode("utf-8", errors="replace")
    assert "ModelViewerElement" in head


def test_vendored_bundle_has_no_sourcemap_pointer():
    """A `//# sourceMappingURL=` comment 500s every page view under devtools.

    The browser follows the pointer to `…/model-viewer-umd.min.js.map`, which is
    not in Dash's `registered_paths`, so `serve_component_suites` raises
    DependencyException. Shipping the map instead would put 4.7 MB in the wheel.
    `scripts/vendor_model_viewer.py` strips the comment; this keeps it stripped.
    """
    bundle = PKG / "vendor" / "model-viewer-umd.min.js"
    tail = bundle.read_bytes()[-4096:]
    assert b"sourceMappingURL" not in tail, (
        "re-vendor with scripts/vendor_model_viewer.py rather than by hand"
    )


def test_vendored_bundle_ships_its_licence():
    licence = PKG / "vendor" / "model-viewer-LICENSE"
    assert licence.is_file()
    assert "Apache License" in licence.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Upstream parity
# --------------------------------------------------------------------------


def test_attributes_dict_is_accepted():
    viewer = dmv.ModelViewer(
        id="v", src="/m.glb", alt="a model",
        attributes={"environment-image": "neutral", "exposure": "1.2"},
    )
    assert viewer.attributes["environment-image"] == "neutral"


def test_mv_wildcard_is_accepted():
    viewer = dmv.ModelViewer(
        id="v", src="/m.glb", alt="a model", mv_environment_image="neutral"
    )
    assert viewer.mv_environment_image == "neutral"


def test_unknown_prop_still_rejected():
    with pytest.raises(TypeError):
        dmv.ModelViewer(id="v", src="/m.glb", alt="a", definitely_not_a_prop=1)


def test_shim_precedence_named_over_wildcard_over_attributes():
    """Named > mv_* > attributes. Order of application in the shim is what
    implements this, so assert the order rather than trusting the comment."""
    shim = (PKG / "dash_model_viewer.js").read_text(encoding="utf-8")
    body = shim[shim.index("function computeAttributes"):]
    body = body[: body.index("return out;")]
    assert body.index("props.attributes") < body.index('indexOf("mv_")')
    assert body.index('indexOf("mv_")') < body.index("NAMED_ATTRS")


# --------------------------------------------------------------------------
# Slot
# --------------------------------------------------------------------------


def test_slot_carries_children_and_a_slot_name():
    """html.Div has no `slot` prop; that is the whole reason Slot exists."""
    from dash import html

    slot = dmv.Slot(slot="hotspot-1", position="0 1 0", children=html.B("Sole"))
    assert slot.slot == "hotspot-1"
    assert slot.position == "0 1 0"
    assert isinstance(slot.children, html.B)


def test_slot_has_n_clicks():
    assert dmv.Slot(slot="hotspot-1").n_clicks == 0


def test_namespaces_match_the_shim():
    shim = (PKG / "dash_model_viewer.js").read_text(encoding="utf-8")
    assert "window.dash_model_viewer" in shim
    for cls in (dmv.ModelViewer, dmv.Slot):
        assert cls._namespace == "dash_model_viewer"
        assert f"{cls._type}: {cls._type}" in shim


def test_serialisation_shape():
    viewer = dmv.ModelViewer(id="v", src="/m.glb", alt="a model")
    payload = viewer.to_plotly_json()
    assert payload["type"] == "ModelViewer"
    assert payload["namespace"] == "dash_model_viewer"
    assert payload["props"]["src"] == "/m.glb"


# --------------------------------------------------------------------------
# configure()
# --------------------------------------------------------------------------


@pytest.mark.filterwarnings("ignore:dash_model_viewer.configure:RuntimeWarning")
def test_configure_switches_to_cdn_and_back():
    try:
        dmv.configure(use_cdn=True)
        assert dmv._VENDOR_RESOURCE["external_only"] is True
        assert "model-viewer" in dmv._VENDOR_RESOURCE["external_url"]

        dmv.configure(use_cdn="https://internal.example/mv.js")
        assert dmv._VENDOR_RESOURCE["external_url"] == "https://internal.example/mv.js"
    finally:
        dmv.configure(use_cdn=False)

    assert "external_url" not in dmv._VENDOR_RESOURCE
    assert dmv._VENDOR_RESOURCE["relative_package_path"].endswith("-umd.min.js")


def test_configure_mutates_the_registered_resource_in_place():
    """hooks.script() holds references; rebinding would be a silent no-op."""
    from dash._hooks import HooksManager

    registered = HooksManager.hooks._js_dist
    before = [r for r in registered if r is dmv._VENDOR_RESOURCE]
    assert before, "vendor resource is no longer the registered object"
