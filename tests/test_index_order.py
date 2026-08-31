"""The script-ordering contract, asserted against a real rendered index.

This is the single most important test in the package, and the one whose
failure is hardest to notice by hand: if the vendored bundle stops executing
before Dash mounts, the symptom is "sometimes the model doesn't render" on
someone else's machine.

What Dash 4.4.1 actually emits (verified, and asserted below):

    polyfill, React, ReactDOM, prop-types,
    dash_renderer bundle, dcc, html, dash_table,
    -> vendored model-viewer UMD          (hook _js_dist, appended last)
    -> dash_model_viewer shim             (hook _js_dist)
    <script id="_dash-renderer"> new DashRenderer(...) </script>

Note the hook scripts land *after* the dash-renderer bundle, not before it.
The race is won because `{%scripts%}` precedes `{%renderer%}` in the index
template, and `{%renderer%}` is the inline statement that actually mounts the
app. A classic script therefore executes first; a `type="module"` script is
deferred past it and the race comes back.
"""

from __future__ import annotations

import re

import pytest
from dash import Dash, html

import dash_model_viewer as dmv
from conftest import BROWSER_UA
from lib.constants import INTERNAL_UA


@pytest.fixture(name="index")
def _index():
    app = Dash(__name__)
    app.layout = html.Div(
        [
            dmv.ModelViewer(
                id="viewer",
                src="/assets/x.glb",
                alt="a model",
                children=[dmv.Slot(slot="hotspot-1", position="0 1 0")],
            )
        ]
    )
    return app.index()


def _positions(index):
    return {
        "react": index.find("/deps/react@"),
        "vendor": index.find("model-viewer-umd"),
        "shim": index.find("dash_model_viewer/dash_model_viewer"),
        "renderer": index.find("new DashRenderer"),
    }


def test_both_resources_are_emitted(index):
    pos = _positions(index)
    assert pos["vendor"] > 0, "vendored model-viewer bundle was not emitted"
    assert pos["shim"] > 0, "shim was not emitted"


def test_react_precedes_the_shim(index):
    """The shim reads window.React at execution time."""
    pos = _positions(index)
    assert 0 < pos["react"] < pos["shim"]


def test_custom_element_defined_before_the_shim(index):
    pos = _positions(index)
    assert 0 < pos["vendor"] < pos["shim"]


def test_everything_precedes_the_renderer_mount(index):
    """`new DashRenderer(...)` is where Dash mounts; both must already have run."""
    pos = _positions(index)
    assert 0 < pos["vendor"] < pos["renderer"]
    assert 0 < pos["shim"] < pos["renderer"]


def test_no_module_or_deferred_scripts(index):
    """Any of these defers execution past the mount and restores the race."""
    assert 'type="module"' not in index
    ours = [
        tag
        for tag in re.findall(r"<script[^>]*>", index)
        if "model-viewer-umd" in tag or "dash_model_viewer/dash_model_viewer" in tag
    ]
    assert len(ours) == 2, ours
    for tag in ours:
        assert "async" not in tag, tag
        assert "defer" not in tag, tag


def test_resources_actually_serve():
    """A fingerprinted URL that 404s is a blank page, not an error."""
    app = Dash(__name__)
    app.layout = html.Div([dmv.ModelViewer(id="v", src="/x.glb", alt="a")])
    index = app.index()

    urls = re.findall(r'src="([^"]*dash_model_viewer[^"]*)"', index)
    assert len(urls) == 2, urls

    client = app.server.test_client()
    # Name the BROWSER lane with the internal token: a bare test client sends
    # `Werkzeug/x.y`, which dash-improve-my-llms >= 2.8 classifies as a
    # crawler (sync item 18's third lane). These are static asset URLs on a
    # bare Dash app, so nothing here 404s today — but "it happens not to
    # matter on this app" is exactly how the fleet's every-page-200 loops
    # were written before the floor moved under them.
    client.environ_base["HTTP_USER_AGENT"] = BROWSER_UA + " " + INTERNAL_UA
    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, (url, response.status_code)
        assert len(response.data) > 0

    bundle = next(u for u in urls if "model-viewer-umd" in u)
    assert len(client.get(bundle).data) > 500_000
