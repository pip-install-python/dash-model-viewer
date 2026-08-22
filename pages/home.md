# dash-model-viewer — interactive 3D models and AR for Dash

> **`dash-model-viewer` — embed interactive 3D models directly into your Dash applications with Augmented Reality (AR) support.** By [Pip Install Python](https://2plot.dev).

A Dash wrapper around Google's [`model-viewer`](https://modelviewer.dev/). Drag
the model above — then note that reading its camera, its dimensions, or a click
on it takes a normal Dash callback and no JavaScript at all.

```bash
pip install dash-model-viewer
```

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
```

That is the whole setup. Importing the package installs the runtime.

---

## What is different in 1.0.0

This release is a rebuild, and it fixes two things that had been broken for the
package's entire published life.

### AR actually works out of the box

`ar_modes` used to default to `"basic_annotations scene-viewer quick-look"`.
`basic_annotations` is not an AR mode — it was the name of a folder in the
repository, copy-pasted into the default. `webxr` was therefore missing, so
in-page WebXR AR never ran unless you happened to override the prop. Nothing
errored; the flagship feature was just quietly degraded everywhere.

The default is now `"webxr scene-viewer quick-look"`, and the test suite
asserts it. → [Augmented reality](/augmented-reality)

### Events reach Python

0.0.1 had **no output props**. Its single `setProps` call was commented out, so
nothing the model did could reach your callbacks. Anything interactive needed a
JavaScript file in `assets/` and a `clientside_callback` to reach it.

The canonical camera-presets example was **230 lines** because of that. It is
now **47 lines of Python**, with no JavaScript.
→ [Camera and views](/camera-and-views)

| Prop | Updates when |
| :-- | :-- |
| `camera` | the user moves the camera (debounced, echo-suppressed) |
| `model_state` | loading, loaded, failed |
| `model_info` | on load — dimensions in metres, variants, animations |
| `ar_status` / `ar_tracking` | an AR session changes state |
| `scene_point` | the model is clicked, with `pick_on_click=True` |
| `Slot.n_clicks` | a hotspot is clicked |

---

## The bundle ships in the wheel

`model-viewer` used to be fetched at runtime from a hard-coded
`ajax.googleapis.com` URL pinned to 3.5.0 — not a declared dependency, not
pinnable by you, and unavailable offline, behind a corporate egress proxy, or
under a strict `script-src` Content-Security-Policy.

Version 4.3.1 is now vendored inside the package and injected by a Dash hook.
It costs about 1 MB per page, which is a real number and is stated plainly on
the [quick start](/quick-start) rather than buried. `configure(use_cdn=...)`
opts back out.

---

## Full upstream parity, permanently

`<model-viewer>` has ~70 attributes and gains more each release. This package
names about twenty and gives you two escape hatches that reach all of the rest
— including attributes that do not exist yet:

```python
dmv.ModelViewer(
    id="viewer", src=..., alt=...,
    mv_environment_image="neutral",          # -> environment-image
    attributes={"orientation": "0deg 0deg 15deg"},
)
```

No regeneration, no release, no waiting.
→ [Attributes and parity](/attributes-and-parity)

---

## Where to go next

| Page | What it covers |
| :-- | :-- |
| [Quick start](/quick-start) | Install, first viewer, and why the script order matters |
| [Events and callbacks](/events-and-callbacks) | Every output prop, and `camera_change_debounce` |
| [Camera and views](/camera-and-views) | Presets, flight, framing an unknown model |
| [Slots and hotspots](/slots-and-hotspots) | Anchoring any Dash component to the geometry |
| [Attributes and parity](/attributes-and-parity) | `attributes` and `mv_*` |
| [Augmented reality](/augmented-reality) | The three AR modes, and the fixed default |
| [Model switching](/model-switching) | Runtime `src` swaps and GLTF variants |
| [Scene Director](/scene-director) | **Generative.** Describe a shot; Claude stages it, grounded in the model's measured geometry |
| [Generative 3D art](/generative-3d) | **Generative.** Describe a sculpture; get a real `.glb` built from primitives |
| [Image to 3D](/image-to-3d) | **Generative.** Upload a picture; Claude reads it and code carves a relief |
| [Benchmark](/benchmark) | One prompt, several models or settings, sculptures side by side |
| [API reference](/api-reference) | Every prop, every payload |
| [Migrating from 0.0.1](/migrating) | Prop-by-prop map |

---

## Credits

Built on Google's [`model-viewer`](https://modelviewer.dev/) (Apache-2.0),
vendored at 4.3.1. Demo models are Google's own `model-viewer` shared assets
and the Khronos Group's glTF Sample Assets; the Materials Variants Shoe is
© 2021 Shopify, CC BY 4.0.

[Source on GitHub](https://github.com/pip-install-python/dash-model-viewer) ·
[PyPI](https://pypi.org/project/dash-model-viewer/)
