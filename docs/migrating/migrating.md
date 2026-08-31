---
name: Migrating from 0.0.1
nav: Migrating
description: A prop-by-prop map from the 0.0.1 API to 1.0.0, and an honest account of why it is a clean break.
endpoint: /migrating
category: Getting started
order: 2
package: dash_model_viewer
icon: mdi:transfer-right
lastmod: 2026-08-08
---

.. llms_copy::Migrating from 0.0.1

.. toc::

### Why a clean break

1.0.0 is not a compatible upgrade. `DashModelViewer` is gone; there is no
shim that keeps old code running.

That is a deliberate decision rather than an oversight, and the argument for
the other choice was real: the package had roughly 253 downloads a month, and a
deprecating wrapper would have cost little. What tipped it was that the parts
most in need of changing — hotspots, AR defaults, and the complete absence of
output props — could not be fixed *while* preserving the old surface. A
compatibility layer would have frozen the exact shapes that made the component
hard to use.

So: rename, and say so loudly.

---

### Side by side

```python
# 0.0.1
from dash_model_viewer import DashModelViewer

DashModelViewer(
    id="viewer",
    src="/assets/shoe.glb",
    alt="A shoe",
    cameraControls=True,
    arModes="webxr scene-viewer quick-look",   # you had to know to set this
    arButtonText="View in your space",
    hotspots=[
        {"slot": "hotspot-1", "position": "0 1 0", "text": "Sole",
         "children_classname": "label"},
    ],
)
```

```python
# 1.0.0
import dash_model_viewer as dmv
from dash import html

dmv.ModelViewer(
    id="viewer",
    src="/assets/shoe.glb",
    alt="A shoe",
    camera_controls=True,
    # ar_modes now defaults to "webxr scene-viewer quick-look"
    children=[
        dmv.Slot(slot="hotspot-1", position="0 1 0",
                 class_name="label", children="Sole"),
        dmv.Slot(slot="ar-button",
                 children=html.Button("View in your space")),
    ],
)
```

---

### Prop map

| 0.0.1 | 1.0.0 | Notes |
| :-- | :-- | :-- |
| `DashModelViewer` | `ModelViewer` | Import name unchanged; class renamed. |
| `cameraControls` | `camera_controls` | All props are `snake_case` now. |
| `touchAction` | `touch_action` | |
| `cameraOrbit` / `cameraTarget` | `camera_orbit` / `camera_target` | Now also **readable** via `camera`. |
| `fieldOfView`, `minFieldOfView`, `maxFieldOfView` | `field_of_view`, … | |
| `minCameraOrbit` / `maxCameraOrbit` | `min_camera_orbit` / `max_camera_orbit` | |
| `interpolationDecay` | `interpolation_decay` | |
| `toneMapping` | `tone_mapping` | |
| `shadowIntensity` | `shadow_intensity` | |
| `arModes` | `ar_modes` | **Default fixed** — see below. |
| `arScale` | `ar_scale` | |
| `variantName` | `variant_name` | |
| `hotspots=[{...}]` | `children=[Slot(...)]` | Now takes any Dash component. |
| `arButtonText="…"` | `Slot(slot="ar-button", children=…)` | |
| `customArPrompt=…` | `Slot(slot="ar-prompt", children=…)` | |
| `customArFailure=…` | `Slot(slot="ar-failure", children=…)` | |
| *(none)* | `camera`, `model_state`, `model_info`, `ar_status`, `ar_tracking`, `scene_point` | The half that never worked. |
| *(none)* | `attributes`, `mv_*` | Full upstream parity. |
| *(none)* | `camera_change_debounce` | Mandatory guard. |
| *(none)* | `pick_on_click` | Arms `scene_point`. |

---

### Hotspot dictionaries → `Slot`

| Old key | New |
| :-- | :-- |
| `slot` | `Slot(slot=...)` |
| `position` | `Slot(position=...)` |
| `normal` | `Slot(normal=...)` |
| `text` | `Slot(children="...")` — or any component |
| `children_classname` | `Slot(class_name=...)` |
| `orbit` / `target` / `fov` | A callback on `Slot.n_clicks` writing the camera props |

The last row is the significant one. Camera-preset hotspots used to be declared
*inside* the hotspot dict and handled invisibly by the component's JavaScript.
They are now an ordinary callback, which means you can log them, animate them,
gate them on auth, or compute them — see
[Camera and views](/camera-and-views).

---

### Delete your clientside callbacks

If you copied the 0.0.1 examples you will have an `assets/model_viewer_clientside.js`
and a `clientside_callback` for anything the component could not report. All of
it is replaceable:

| You were doing this in JS | Now |
| :-- | :-- |
| Reading `getCameraOrbit()` into a `dcc.Store` | `Input("viewer", "camera")` |
| `getDimensions()` for a bounding box | `Input("viewer", "model_info")` |
| `availableVariants` for a dropdown | `model_info["variants"]` |
| Listening for `load` / `progress` | `Input("viewer", "model_state")` |
| Listening for `ar-status` / `ar-tracking` | `ar_status` / `ar_tracking` |
| `positionAndNormalFromPoint()` on click | `pick_on_click=True` → `scene_point` |
| Wiring hotspot clicks | `Slot.n_clicks` |

---

### The AR default

Worth calling out separately because it changes behaviour silently rather than
loudly. 0.0.1 shipped:

```python
arModes = "basic_annotations scene-viewer quick-look"
```

`basic_annotations` is not an AR mode — it was a folder name in `usage_tests/`.
`webxr` was therefore absent, and in-page WebXR AR never ran in a default
configuration. If your code explicitly set `arModes`, you were unaffected; if
it did not, you were running without WebXR and had no way to know.

You can now delete any explicit `ar_modes="webxr scene-viewer quick-look"` —
that is the default. See [Augmented reality](/augmented-reality).

---

### Things that no longer exist

- `dash_model_viewer.DashModelViewer` — renamed.
- The generated R and Julia bindings — removed; they were generated and unused.
- `package-info.json` inside the package — `__version__` now comes from
  installed metadata.
- The runtime CDN fetch of `model-viewer` 3.5.0 — the bundle ships in the wheel
  at 4.3.1. If you relied on the CDN behaviour, `dmv.configure(use_cdn=True)`
  restores it.
