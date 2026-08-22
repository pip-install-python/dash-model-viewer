# dash-model-viewer — interactive 3D models and AR for Dash

Embed interactive 3D models directly into your Dash applications with
Augmented Reality (AR) support.

A Dash wrapper around Google's [`<model-viewer>`](https://modelviewer.dev/).
The web component ships **inside the wheel** — no CDN request at runtime, works
offline, works behind an egress proxy, works under a strict `script-src` CSP,
and the version is pinned by your lockfile.

📚 **[modelviewer.2plot.dev](https://modelviewer.2plot.dev)** — full docs and live examples

```bash
pip install dash-model-viewer
```

## Quick start

```python
from dash import Dash, html
import dash_model_viewer as dmv

app = Dash(__name__)

app.layout = html.Div([
    dmv.ModelViewer(
        id="viewer",
        src="/assets/astronaut.glb",
        alt="A 3D model of an astronaut",
        style={"width": "100%", "height": "480px"},
    )
])

if __name__ == "__main__":
    app.run(debug=True)
```

Importing the package is all the setup there is — the runtime is injected by a
Dash hook. AR is on by default and, as of 1.0.0, actually works: `ar_modes`
defaults to `"webxr scene-viewer quick-look"`.

## Events come back as props

Every interaction is a normal Dash `Input`. No `clientside_callback` required.

```python
from dash import Input, Output, callback

@callback(Output("readout", "children"), Input("viewer", "camera"))
def show_camera(camera):
    if not camera:
        return "Drag the model."
    return f"orbit {camera['orbit']} · fov {camera['field_of_view']}"
```

| Prop | Updates when |
|---|---|
| `camera` | the user moves the camera (debounced; programmatic moves are suppressed) |
| `model_state` | loading progress, load success, load failure |
| `model_info` | on load — real dimensions in metres, GLTF variants, animation names |
| `ar_status` / `ar_tracking` | an AR session starts, places, fails, or loses tracking |
| `scene_point` | the user clicks the model, when `pick_on_click=True` |

> **`camera_change_debounce`** defaults to 100 ms and should stay non-zero.
> `camera-change` fires at frame rate, so `0` means one server callback per
> frame per viewer.

## Hotspots and slots

`<model-viewer>` places its extras into named slots. `Slot` puts any Dash
component into any of them — and `n_clicks` makes a hotspot a callback input:

```python
import dash_mantine_components as dmc

dmv.ModelViewer(
    id="viewer", src="/assets/shoe.glb", alt="A running shoe",
    children=[
        dmv.Slot(id="sole", slot="hotspot-sole",
                 position="0 0.05 0.1", normal="0 1 0",
                 children=dmc.Badge("Carbon plate", color="teal")),
        dmv.Slot(slot="ar-button",
                 children=dmc.Button("View in your space")),
    ],
)
```

## Every model-viewer attribute, forever

Named props cover the common attributes. For everything else — including
attributes Google adds *after* this release — there are two escape hatches that
need no new version of this package:

```python
dmv.ModelViewer(
    id="viewer", src="/assets/shoe.glb", alt="A running shoe",

    mv_environment_image="neutral",          # -> environment-image="neutral"
    mv_auto_rotate_delay="0",                # -> auto-rotate-delay="0"

    attributes={                              # raw kebab-case passthrough
        "orientation": "0deg 0deg 15deg",
        "exposure": "1.2",
    },
)
```

Precedence when the same attribute is set twice: **named prop > `mv_*` >
`attributes`**.

## Serving the bundle elsewhere

The vendored bundle is ~1 MB and is served by your own app. To use a CDN or an
internal mirror instead:

```python
import dash_model_viewer as dmv

dmv.configure(use_cdn=True)                        # public jsDelivr
dmv.configure(use_cdn="https://cdn.example/mv.js") # your mirror

app = Dash(__name__)
```

Call it at module scope, before the first request is served.

## Compatibility

| | |
|---|---|
| Python | 3.9 – 3.13 |
| Dash | 4.1 – 4.4 |
| `@google/model-viewer` | 4.3.1, vendored |

## Upgrading from 0.0.1

1.0.0 is a clean break: `snake_case` props, `DashModelViewer` → `ModelViewer`,
and hotspot dictionaries → `Slot` components. The full prop-by-prop table is in
[CHANGELOG.md](CHANGELOG.md).

The headline fix: `ar_modes` used to default to
`"basic_annotations scene-viewer quick-look"`. `basic_annotations` is not an AR
mode — it was a folder name pasted into the default — so `webxr` was missing
and WebXR AR was silently disabled on Android in every default configuration.

## Development

There is no build step. No `package.json`, no webpack, no
`dash-generate-components`. The vendored bundle, the shim
(`dash_model_viewer/dash_model_viewer.js`) and the Python components
(`dash_model_viewer/_components.py`) are each edited directly.

```bash
pip install -e ".[dev]"
pytest -q
```

## Licence

Apache-2.0. Bundles `@google/model-viewer`, also Apache-2.0 — see
`dash_model_viewer/vendor/model-viewer-LICENSE`.

Built by [Pip Install Python](https://github.com/pip-install-python).
