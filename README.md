<div align="center">

<a href="https://2plot.ai">
  <img src="https://cdn.2plot.ai/github_assets/favicons/modelviewer.png" alt="dash-model-viewer" width="120">
  <img src="https://cdn.2plot.ai/github_assets/dark_mode_2plot.png" alt="2plot.ai" width="300">
</a>


# dash-model-viewer

**dash-model-viewer — interactive 3D models and AR for Dash**

Google's [`<model-viewer>`](https://modelviewer.dev/) as a first-class component for [Plotly Dash](https://dash.plotly.com) 4.

The web component ships **inside the wheel** · every interaction arrives as an ordinary Dash prop · hotspots are components, not dictionaries · unknown attributes pass through untouched · no `clientside_callback` required for anything.

[![PyPI version](https://img.shields.io/pypi/v/dash-model-viewer?color=blue)](https://pypi.org/project/dash-model-viewer/)
[![Python](https://img.shields.io/pypi/pyversions/dash-model-viewer)](https://pypi.org/project/dash-model-viewer/)
[![Dash 4.x](https://img.shields.io/badge/Dash-4.1%20%E2%80%93%204.4-1a1a2e?logo=plotly&logoColor=white)](https://dash.plotly.com/)
[![model-viewer 4.3.1](https://img.shields.io/badge/model--viewer-4.3.1%20vendored-4c6ef5)](https://github.com/google/model-viewer)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](LICENSE)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/WEnZR35mrK)
[![YouTube](https://img.shields.io/badge/YouTube-%402plotai-FF0000?logo=youtube&logoColor=white)](https://www.youtube.com/channel/UC6Bmo0t0ZUpU_xKBYW0bJuQ)

**[Documentation](https://modelviewer.2plot.dev)** · [Discord](https://discord.gg/WEnZR35mrK) · [YouTube](https://www.youtube.com/channel/UC6Bmo0t0ZUpU_xKBYW0bJuQ) · [GitHub](https://github.com/pip-install-python/dash-model-viewer)

<br/>

<a href="https://modelviewer.2plot.dev">
  <img src="https://cdn.2plot.ai/github_assets/modelviewer.2plot.dev.png" alt="dash-model-viewer running live at modelviewer.2plot.dev" width="880">
</a>

_Live at **[modelviewer.2plot.dev](https://modelviewer.2plot.dev)** — every model on the docs site is a running Dash app._

<br/>

_Maintained by **[Pip Install Python LLC](https://github.com/2plotai)**._

</div>

---

## Overview

`<model-viewer>` is a **custom element**, not a React component. Wrapping it for Dash means
answering two questions honestly: **how does the runtime get onto the page, and how does a
DOM event become a Python prop?**

Version 0.0.1 answered the first with a hard-coded CDN `<script>` injected into
`document.body` by every component instance, and the second not at all — its `setProps`
call was commented out, so the component had no output props. 1.0.0 answers both:

| Upstream shape | What Python sees | Why |
|---|---|---|
| A custom element defined by a script that must run **before** Dash mounts | The bundle **vendored in the wheel**, emitted through `dash.hooks.script()` as a **classic** script | Classic scripts execute in document order, before the inline `{%renderer%}` statement that mounts the app. A `type="module"` or `async` resource defers past it and the element is undefined at mount — an intermittent "sometimes the model doesn't render". |
| DOM events (`camera-change`, `load`, `ar-status`, …) | **Output props** — `camera`, `model_state`, `model_info`, `ar_status`, `ar_tracking`, `scene_point` | An event listener cannot be serialized. The state it carries can. `camera` is debounced because `camera-change` fires at frame rate. |
| Named slots (`hotspot-*`, `ar-button`, `poster`) | **`Slot`** — a component holding arbitrary Dash children | `dash.html.Div` has no `slot` prop, which is the only reason the old wrapper needed hotspots to be dictionaries. Slots take real components now. |
| A kebab-case attribute surface that keeps growing upstream | **`mv_*` props** and an **`attributes` dict** | Named props cannot cover an upstream that keeps growing. These two escape hatches mean a new `<model-viewer>` attribute needs no release of this package. |

The result is that a Dash developer writes ordinary `@callback`s and never touches
JavaScript. The [camera-views example](https://modelviewer.2plot.dev/camera-and-views) went
from 230 lines to 47 in the rewrite, and lost its clientside layer entirely.

## Installation

```bash
pip install dash-model-viewer
```

> **1.0.0 is not on PyPI yet.** The published release is still `0.0.1` — the version
> described under *Upgrading* below, with the CDN dependency and no output props. Until
> 1.0.0 ships, install from source:
>
> ```bash
> pip install git+https://github.com/pip-install-python/dash-model-viewer
> ```
>
> Everything documented here describes 1.0.0. Delete this note when the release is
> published.

Nothing else is required. The `@google/model-viewer` bundle (4.3.1, ~1 MB) ships inside the
wheel, so there is no CDN request at load time, no `external_scripts` entry to add, and no
build step for consumers. It works offline, behind a corporate egress proxy, and under a
strict `script-src` Content-Security-Policy — and the version is pinned by your lockfile
rather than by whatever a CDN is serving today.

## Quick Start

```python
from dash import Dash, html
import dash_model_viewer as dmv

app = Dash(__name__)

app.layout = html.Div([
    dmv.ModelViewer(
        id="viewer",
        src="/assets/astronaut.glb",
        alt="A 3D model of an astronaut",
        camera_controls=True,
        style={"width": "100%", "height": "480px"},
    )
])

if __name__ == "__main__":
    app.run(debug=True)
```

Importing the package is all the setup there is — the runtime is injected by a Dash hook at
import time. AR is on by default and, as of 1.0.0, actually works.

Reading the model back is an ordinary callback:

```python
from dash import Input, Output, callback

@callback(Output("readout", "children"), Input("viewer", "camera"))
def show_camera(camera):
    if not camera:
        return "Drag the model."
    return f"orbit {camera['orbit']} · fov {camera['field_of_view']}"
```

## Documentation

### 📚 **[modelviewer.2plot.dev](https://modelviewer.2plot.dev)**

Thirteen pages, each one a running Dash app you can drag: quick start, attributes and
parity, events and callbacks, camera and views, slots and hotspots, augmented reality,
model switching, image-to-3D, generative 3D, a scene director, benchmarks, the full API
reference, and a prop-by-prop migration guide.

Append `/llms.txt` to any page URL for the machine-readable Markdown of that page — the
whole site is built to be read by agents as well as people.

To run the docs site locally:

```bash
pip install -r requirements.txt
# markdown2dash pins gunicorn<22, against the CVE-driven gunicorn>=23 floor in
# requirements.txt. pip cannot resolve both, so it installs without its
# dependency graph — every one of its real dependencies is already pinned there.
pip install --no-deps markdown2dash==0.1.2
pip install .          # the site documents the package in THIS checkout
python run.py
```

## The prop surface

32 props on `ModelViewer`, 8 on `Slot`. Grouped by what they're for:

### Source and framing

| Prop | Type | Notes |
|---|---|---|
| `src` | `str` | Path or absolute URL to a `.glb` / `.gltf` |
| `alt` | `str` | **Set this.** It is the accessible name of an otherwise opaque canvas |
| `poster` | `str` | Shown until the model is interactive |
| `style`, `class_name` | `dict` / `str` | The element is `display: block` with no intrinsic size — give it a height |

### Camera

`camera_controls` · `touch_action` · `camera_orbit` · `camera_target` · `field_of_view` ·
`min_field_of_view` · `max_field_of_view` · `min_camera_orbit` · `max_camera_orbit` ·
`interpolation_decay`

### Rendering and AR

`ar` · `ar_modes` · `ar_scale` · `tone_mapping` · `shadow_intensity` · `variant_name`

### Output props — read-only from Python

Written by the component via `setProps`. Each is an ordinary callback `Input`.

| Prop | Updates when |
|---|---|
| `camera` | the user moves the camera (debounced; programmatic moves are suppressed) |
| `model_state` | loading progress, load success, load failure |
| `model_info` | on load — real dimensions in metres, GLTF variants, animation names |
| `ar_status` / `ar_tracking` | an AR session starts, places, fails, or loses tracking |
| `scene_point` | the user clicks the model, when `pick_on_click=True` |

### Escape hatches

| Prop | Shape | Example |
|---|---|---|
| `mv_*` | `mv_<snake_case>` → `<kebab-case>` | `mv_environment_image="neutral"` → `environment-image="neutral"` |
| `attributes` | raw `dict`, kebab-case keys | `{"orientation": "0deg 0deg 15deg", "exposure": "1.2"}` |

Precedence when the same attribute is set twice: **named prop > `mv_*` > `attributes`**.

### `Slot`

`slot` · `position` · `normal` · `children` · `n_clicks` · `style` · `class_name`

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

`n_clicks` makes a hotspot a callback input like any `dmc.Button`.

## Serving the bundle elsewhere

The vendored bundle is served by your own app. To use a public CDN or an internal mirror
instead:

```python
import dash_model_viewer as dmv

dmv.configure(use_cdn=True)                         # public jsDelivr
dmv.configure(use_cdn="https://cdn.example/mv.js")  # your mirror

app = Dash(__name__)
```

Call it at module scope, **before** `Dash()` is constructed — the hook that emits the
script fires during app construction, so a later call has nothing left to change.

## Dash compatibility

| | |
|---|---|
| **Dash** | 4.1 – 4.4 (`dash.hooks.script` is what the architecture rests on) |
| **Python** | 3.9 – 3.13 |
| **`@google/model-viewer`** | 4.3.1, pinned exactly and bundled |

The wheel depends on Dash and nothing else. The documentation site's requirements are
separate and never reach a `pip install dash-model-viewer`.

## Upgrading from 0.0.1

1.0.0 is a clean break: `snake_case` props, `DashModelViewer` → `ModelViewer`, and hotspot
dictionaries → `Slot` components. The full prop-by-prop table is in
[CHANGELOG.md](CHANGELOG.md), and [`/migrating`](https://modelviewer.2plot.dev/migrating)
walks it with runnable examples.

Three defects are fixed along the way, and they are the reason the break was worth it:

- **AR works out of the box on Android.** `ar_modes` defaulted to
  `"basic_annotations scene-viewer quick-look"`. `basic_annotations` is not an AR mode — it
  was a folder name in `usage_tests/` pasted into the default — so `webxr` was absent from
  every default configuration and the flagship feature had never worked without the user
  discovering and overriding the prop. The default is now `"webxr scene-viewer quick-look"`.
- **Events reach Python.** `setProps` was commented out, so the component had no output
  props at all and every interaction needed a `clientside_callback`.
- **Listeners no longer accumulate.** `removeEventListener` was called with a freshly
  created closure on every render, so it removed nothing.

## Common gotchas

- **Give the element a height.** `<model-viewer>` is `display: block` with no intrinsic
  size. Without a height it renders at zero pixels and looks like a load failure.
- **`camera_change_debounce` should stay non-zero.** It defaults to 100 ms.
  `camera-change` fires at frame rate, so `0` means one server callback per frame, per
  viewer, per user.
- **`alt` is not optional in practice.** It is the accessible name for a canvas that
  screen readers and agents cannot otherwise describe.
- **`configure()` must run before `Dash()`.** After construction the script resource is
  already emitted.
- **Don't reach for `clientside_callback` out of habit.** If you are writing one to read
  camera state or hotspot clicks, there is a prop for it.

## Development

There is no build step. No `package.json`, no webpack, no babel, no
`dash-generate-components`, no `metadata.json` — three hand-authored layers and zero
generated ones:

```
dash_model_viewer/vendor/model-viewer-umd.min.js   Google's UMD build, 4.3.1, verbatim
dash_model_viewer/dash_model_viewer.js             the shim — registers the namespace
dash_model_viewer/_components.py                   hand-written Component subclasses
```

```bash
pip install -e ".[dev]"
pytest -q
```

`.claude/ARCHITECTURE.md` holds the design record: why vendoring is a supply-chain fix
rather than a preference, why the script must be classic rather than a module, and what
each layer is responsible for.

## Community & support

- **Discord** — [join](https://discord.gg/WEnZR35mrK)
- **YouTube** — [@2plotai](https://www.youtube.com/channel/UC6Bmo0t0ZUpU_xKBYW0bJuQ)
- **Issues** — [GitHub](https://github.com/pip-install-python/dash-model-viewer/issues)

## More from Pip Install Python LLC

Part of the [2plot network](https://2plot.dev) — component documentation sites, each one a
running Dash app: [leaflet](https://leaflet.2plot.dev) ·
[pannellum](https://pannellum.2plot.dev) · [excalidraw](https://excalidraw.2plot.dev) ·
[muicharts](https://muicharts.2plot.dev) · [flexlayout](https://flexlayout.2plot.dev) ·
[emojimart](https://emojimart.2plot.dev) · [flows](https://flows.2plot.dev) ·
[email](https://email.2plot.dev) · [scheduler](https://muischeduler.2plot.dev) ·
[llms](https://llms.2plot.dev) · [boilerplate](https://boilerplate.2plot.dev)

## License

Apache-2.0 — see [LICENSE](LICENSE).

`@google/model-viewer` is also Apache-2.0, by the Google model-viewer team. Its licence
ships alongside the bundle in `dash_model_viewer/vendor/model-viewer-LICENSE`.
