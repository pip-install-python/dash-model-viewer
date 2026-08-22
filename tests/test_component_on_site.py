"""The docs site is the package's integration test.

Every example page builds a real `ModelViewer` at import time, so a page that
renders proves the hook fired, the vendored bundle resolved, and the shim was
emitted — under the same `run.py` production uses.

This is the file that makes docs/ a regression suite rather than prose. If the
package's public API changes and these examples are not updated, they stop
importing and the whole site fails to boot, loudly, in CI.
"""

from __future__ import annotations

import re

import pytest

import dash_model_viewer as dmv

# Pages that must render a viewer. Deliberately not "every page": /api-reference
# and /migrating are prose, and asserting a viewer on them would be a test of
# this list rather than of the site.
# NOT /benchmark or /api-reference: the benchmark builds its viewers inside the
# results callback, so its initial layout correctly has none.
VIEWER_PAGES = [
    "/",
    "/quick-start",
    "/events-and-callbacks",
    "/camera-and-views",
    "/slots-and-hotspots",
    "/attributes-and-parity",
    "/augmented-reality",
    "/model-switching",
    "/scene-director",
    "/generative-3d",
    "/image-to-3d",
]


# /quick-start DOCUMENTS the script order, so its prose contains
# "model-viewer-umd", "new DashRenderer(...)" and friends as ordinary content.
# Every check below therefore parses <script> TAGS rather than substrings — a
# raw `in` test passes for the wrong reason on this site, and would keep
# passing if the runtime stopped being emitted at all.
SCRIPT_SRC = re.compile(r'<script[^>]*\bsrc="([^"]+)"[^>]*>')
RENDERER_TAG = re.compile(r'<script[^>]+id="_dash-renderer"')


def _script_srcs(html: str) -> list[str]:
    return SCRIPT_SRC.findall(html)


def _ours(html: str) -> list[str]:
    return [
        src
        for src in _script_srcs(html)
        if "/dash_model_viewer/" in src
    ]


def test_the_runtime_is_emitted_once(client):
    """Both scripts, exactly once each — a duplicate means double-registration."""
    srcs = _ours(client.get("/quick-start").text)
    vendor = [s for s in srcs if "model-viewer-umd" in s]
    shim = [s for s in srcs if "/dash_model_viewer/dash_model_viewer." in s]
    assert len(vendor) == 1, vendor
    assert len(shim) == 1, shim


def test_the_runtime_is_a_classic_script(client):
    """`type=module`, `async` or `defer` would defer past `new DashRenderer()`."""
    html = client.get("/quick-start").text
    ours = [
        tag
        for tag in re.findall(r"<script[^>]*>", html)
        if "/dash_model_viewer/" in tag
    ]
    assert len(ours) == 2, ours
    for tag in ours:
        assert "type=" not in tag, tag
        assert "async" not in tag, tag
        assert "defer" not in tag, tag


def test_the_element_is_defined_before_dash_mounts(client):
    """Ordering, asserted on the served document rather than on the theory."""
    html = client.get("/quick-start").text
    srcs = _script_srcs(html)
    vendor_i = next(i for i, s in enumerate(srcs) if "model-viewer-umd" in s)
    shim_i = next(i for i, s in enumerate(srcs)
                  if "/dash_model_viewer/dash_model_viewer." in s)
    assert vendor_i < shim_i, (vendor_i, shim_i)

    # The renderer is the inline tag Dash emits last; both of ours precede it.
    mount = RENDERER_TAG.search(html)
    assert mount, "no _dash-renderer script in the document"
    for src in _ours(html):
        assert html.find(src) < mount.start(), f"{src} is emitted after the mount"


def test_the_runtime_actually_downloads(client):
    """A fingerprinted URL that 404s renders a blank box, not an error."""
    urls = _ours(client.get("/quick-start").text)
    assert len(urls) == 2, urls
    for url in urls:
        response = client.get(url)
        assert response.ok, (url, response.status)

    bundle = next(u for u in urls if "model-viewer-umd" in u)
    assert len(client.get(bundle).text) > 400_000, "vendored bundle looks truncated"


def _walk(node):
    """Yield every component in a registered page layout."""
    from dash.development.base_component import Component

    if isinstance(node, Component):
        yield node
        for child in (getattr(node, "children", None) or []) if isinstance(
            getattr(node, "children", None), (list, tuple)
        ) else ([node.children] if getattr(node, "children", None) is not None else []):
            yield from _walk(child)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk(item)


@pytest.mark.parametrize("path", VIEWER_PAGES)
def test_example_pages_render_a_viewer(client, path):
    """Walk the REGISTERED LAYOUT, not the served HTML.

    Substring-matching "ModelViewer" in the response passes for the wrong
    reason on this site: several pages quote the class name in their prose, and
    `.. source::` inlines example modules that construct one. /benchmark passed
    that check while having no viewer in its layout at all.
    """
    import dash

    entry = next(e for e in dash.page_registry.values() if e["path"] == path)
    layout = entry["layout"]
    layout = layout() if callable(layout) else layout
    viewers = [c for c in _walk(layout) if type(c).__name__ == "ModelViewer"]
    assert viewers, f"{path} registers no ModelViewer in its layout"
    for viewer in viewers:
        assert viewer._namespace == "dash_model_viewer"
        assert getattr(viewer, "alt", None), f"{path}: a ModelViewer with no alt text"


def test_the_documented_ar_default_is_the_real_one(client):
    """Docs and code disagreed for the whole life of 0.0.1. Pin them together."""
    assert dmv.DEFAULT_AR_MODES == "webxr scene-viewer quick-look"
    prose = client.get("/augmented-reality/llms.txt").text
    assert dmv.DEFAULT_AR_MODES in prose
    assert "basic_annotations" in prose, "the page should still explain the old bug"


def test_the_documented_vendored_version_is_the_real_one(client):
    prose = client.get("/quick-start/llms.txt").text
    assert dmv.MODEL_VIEWER_VERSION in prose, (
        f"docs do not name the vendored version {dmv.MODEL_VIEWER_VERSION}"
    )


def test_examples_use_licensed_demo_models_only(client):
    """A public indexed site must not serve the 0.0.1 character models.

    Two of them are commercial game characters that were committed to this
    repository with no attribution. They are gone from `assets/`; this keeps
    them gone.
    """
    from lib import demo_models

    urls = [v for k, v in vars(demo_models).items() if k.isupper() and isinstance(v, str)]
    assert urls, "demo_models exposes no model URLs"
    for url in urls:
        assert url.startswith("https://"), url
        assert "modelviewer.dev" in url or "KhronosGroup" in url, (
            f"{url} is not from Google's or Khronos' published sample sets"
        )

    for banned in ("kara", "detroit", "thor_and_the_midgard"):
        assert not any(banned in u.lower() for u in urls), banned


# --------------------------------------------------------------------------
# Busy state on anything that calls a model
# --------------------------------------------------------------------------

#: (page, the callback's first Output) for every model-backed generation.
MODEL_BACKED = [
    ("/generative-3d", "g3-viewer.src"),
    ("/image-to-3d", "i3-viewer.src"),
    ("/scene-director", "sd-viewer.camera_orbit"),
    ("/benchmark", "bm-results.children"),
]


@pytest.mark.parametrize("path,output", MODEL_BACKED)
def test_model_backed_callbacks_declare_a_busy_state(client, path, output):
    """A call that takes ten seconds with no feedback reads as a broken page.

    Reported from the running site: clicking Sculpt did nothing visible until
    the model came back, and there was no way to tell a slow call from a dead
    one. `running=` is the fix; this keeps it attached.

    The check reads `/_dash-dependencies` rather than the layout, because the
    busy props are set by Dash from the callback's `running` block and never
    appear as ordinary Outputs.
    """
    import json

    deps = json.loads(client.get("/_dash-dependencies").text)
    match = [d for d in deps if output in (d.get("output") or "")]
    assert match, f"no callback outputs {output}"

    running = match[0].get("running")
    assert running, f"{path}: the generation callback declares no running state"

    on = running["running"]
    off = running["runningOff"]
    assert on.keys() == off.keys(), "every running prop needs an off value"

    # The guarantee is that something VISIBLE changes, not which mechanism
    # provides it. A LoadingOverlay suits a page with a viewer already on
    # screen; /benchmark starts with an empty results area, where a dcc.Loading
    # spinner is the natural fit and an overlay would have nothing to cover.
    #
    # `disabled` deliberately does not count. A greyed-out button is the exact
    # failure that was reported: it looks the same as a page that has hung.
    visible = {k for k in on if k.rsplit(".", 1)[-1] in ("visible", "loading", "display")}
    assert visible, (
        f"{path}: the running state only toggles {sorted(on)} — none of which "
        "is visible feedback. A disabled control looks identical to a hung page."
    )
    assert all(off[k] is False for k in off if k.endswith(".visible"))
    assert all(off[k] is False for k in off if k.endswith(".loading"))


def test_running_props_do_not_collide_with_real_outputs(client):
    """A prop in `running` that the callback also returns races with itself."""
    import json

    deps = json.loads(client.get("/_dash-dependencies").text)
    for dep in deps:
        running = dep.get("running")
        if not running:
            continue
        outputs = set((dep.get("output") or "").strip(".").split("..."))
        clash = {k for k in running["running"] if k in outputs}
        assert not clash, f"running props also returned by the callback: {clash}"
