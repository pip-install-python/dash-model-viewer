---
name: Camera and Views
description: Camera presets, flight between them, and the 230-line clientside example that became 47 lines of Python.
endpoint: /camera-and-views
package: dash_model_viewer
icon: mdi:camera-control
lastmod: 2026-08-08
---

.. llms_copy::Camera and Views

.. toc::

### 230 lines to 47

This exact example — an astronaut with clickable camera presets — was the
canonical `dash-model-viewer` demo. Under 0.0.1 it was **230 lines**, almost
all of it a `clientside_callback` and a hand-written JavaScript file in
`assets/`, because the component could neither report its camera nor accept a
click.

It is now **47 lines of Python**, no JavaScript, no `assets/` file.

.. exec::docs.camera-and-views.camera_views
    :code: false

.. source::docs/camera-and-views/camera_views.py

The whole mechanism is a pattern-matching callback returning three props. There
is nothing clever left in it, which is the point.

---

### The camera props

| Prop | Format | Notes |
| :-- | :-- | :-- |
| `camera_orbit` | `"theta phi radius"` | e.g. `"45deg 75deg 2.5m"`. `phi` is measured from +Y, so `0deg` is directly overhead and `90deg` is level with the model. |
| `camera_target` | `"X Y Z"` | Metres. The point the camera looks at and orbits around. |
| `field_of_view` | `"30deg"` | Smaller is more telephoto — and more flattering for a product shot. |
| `min_camera_orbit` / `max_camera_orbit` | `"auto auto auto"` | Per-component limits; `auto` means "no limit on this axis". |
| `min_field_of_view` / `max_field_of_view` | `"25deg"` / `"auto"` | Zoom limits. |
| `interpolation_decay` | number | **The one that makes it feel good.** |

---

### `interpolation_decay` is what turns a cut into a flight

Set the camera props with no `interpolation_decay` and the view *jumps*. The
model appears to teleport, and users read that as a bug even when it is not.

`interpolation_decay` is the time constant of the camera's easing. Lower is
slower and more cinematic; higher snaps harder; `0` is instant.

```python
dmv.ModelViewer(..., interpolation_decay=120)   # unhurried, used above
dmv.ModelViewer(..., interpolation_decay=50)    # brisk
dmv.ModelViewer(..., interpolation_decay=0)     # jump cut
```

This is the single highest-return prop on the page for perceived quality, and
it costs nothing at runtime.

---

### Reading and writing the camera in the same callback

This is safe, and it is the pattern that was impossible in 0.0.1:

```python
@callback(
    Output("viewer", "camera_orbit"),
    Input("viewer", "camera"),
    Input("snap-to-front", "n_clicks"),
)
def maybe_snap(camera, _):
    if ctx.triggered_id == "snap-to-front":
        return "0deg 80deg 3m"
    ...
```

Writing `camera_orbit` moves the camera, which fires `camera-change`, which
would normally update `camera` and re-enter the callback — a loop bounded only
by network latency. The shim suppresses it: only events whose
`event.detail.source` is `user-interaction` are reported. Programmatic moves
are silent by construction, so you do not need `prevent_initial_call` gymnastics
or a `dcc.Store` guard flag.

See [Events and callbacks](/events-and-callbacks) for `camera_change_debounce`,
the other half of not melting your server.

---

### Framing a model you have never seen

Hard-coded orbits assume you know the model's size. When users supply their own
files, read the bounding box instead — `model_info` gives it to you in metres:

```python
@callback(
    Output("viewer", "camera_orbit"),
    Output("viewer", "camera_target"),
    Input("viewer", "model_info"),
)
def frame_it(info):
    if not info or not info.get("dimensions"):
        raise PreventUpdate
    d = info["dimensions"]
    radius = max(d["x"], d["y"], d["z"]) * 1.8
    return f"0deg 78deg {radius:.2f}m", f"0m {d['y'] / 2:.2f}m 0m"
```

Grounding a camera in the model's *measured* size, rather than in a number
somebody typed once, is also the prerequisite for letting anything else choose
the angle for you.
