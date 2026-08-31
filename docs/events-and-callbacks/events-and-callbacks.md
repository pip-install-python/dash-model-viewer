---
name: Events and Callbacks
nav: Events
description: The camera, load state, model dimensions, AR status and hotspot clicks arrive as ordinary Dash props — no clientside callbacks.
endpoint: /events-and-callbacks
category: Interaction
order: 1
package: dash_model_viewer
icon: mdi:transit-connection-variant
lastmod: 2026-08-08
---

.. llms_copy::Events and Callbacks

.. toc::

### The headline change in 1.0.0

Version 0.0.1 had **no output props at all**. The single `setProps` call in the
component was commented out, so nothing the model did could reach Python. Every
interaction — reading the camera, reacting to a load, measuring the model —
required hand-written JavaScript in `assets/` and a `clientside_callback` to
reach it.

That is why the previous camera-views example was 231 lines.

Everything below is now an ordinary `Input`.

| Prop | Updates when | Shape |
| :-- | :-- | :-- |
| `camera` | the user moves the camera | `{"orbit", "target", "field_of_view", "source"}` |
| `model_state` | loading, loaded, or failed | `{"status", "progress"}` |
| `model_info` | on load | `{"dimensions", "variants", "animations"}` |
| `ar_status` | an AR session changes state | `str` |
| `ar_tracking` | AR gains or loses tracking | `str` |
| `scene_point` | the model is clicked, with `pick_on_click=True` | `{"position", "normal", "uv"}` |
| `Slot.n_clicks` | a slot is clicked | `int` |

---

### Reading the camera

.. exec::docs.events-and-callbacks.camera_readout
    :code: false

.. source::docs/events-and-callbacks/camera_readout.py

Eleven lines of callback for something that used to need a JavaScript file, a
`dcc.Store`, and a `ClientsideFunction`.

---

### `camera_change_debounce` — the prop you must not set to 0

`camera-change` fires **at frame rate**. Unthrottled, a single viewer in a
single browser tab is 60 server round-trips per second.

The default is `100` ms. Setting it to `0` is permitted, documented, and means
exactly what it sounds like.

```python
dmv.ModelViewer(..., camera_change_debounce=120)   # coalesce for 120 ms
dmv.ModelViewer(..., camera_change_debounce=0)     # you are asking for the storm
```

.. admonition::The infinite loop, and why you will not hit it
    :icon: radix-icons:info-circled
    :color: blue

    `camera_orbit` is two-way. Naively, a callback that *writes* `camera_orbit`
    causes `camera-change` to fire, which updates `camera`, which re-triggers
    the callback — forever, as fast as the browser can manage.

    The shim suppresses this by checking `event.detail.source` and reporting
    **only** `user-interaction` events. Programmatic camera moves — from a
    callback, from a hotspot, from the generative demo — never echo back. You
    can safely make `camera` an `Input` and `camera_orbit` an `Output` of the
    same callback.

---

### Load progress and real dimensions

`model_info` carries the model's **measured bounding box in metres**, plus its
GLTF material variants and animation clips. This is the prop that deletes the
most user code: getting a model's size previously meant reaching into the
element's JavaScript API and marshalling the result back through a store.

.. exec::docs.events-and-callbacks.load_state
    :code: false

.. source::docs/events-and-callbacks/load_state.py

`model_state["status"]` is one of `loading`, `loaded` or `error`. Note that
`progress` events stop at 1.0 — completion is reported once, by `load`, so a
callback keyed on `model_state` does not fire twice at the end of every load.

---

### Picking a point on the surface

With `pick_on_click=True`, clicking the model reports the 3D position and
surface normal under the cursor — the raw material for placing a hotspot where
the user pointed.

```python
dmv.ModelViewer(id="v", src=..., alt=..., pick_on_click=True)

@callback(Output("store", "data"), Input("v", "scene_point"))
def remember(point):
    # {"position": "0.12m 1.04m 0.33m", "normal": "0 1 0", "uv": [0.5, 0.5]}
    return point
```

Returns `None` when the click misses the mesh, which is the common case near
the edges — check before using it.

---

### What is deliberately *not* here

There is no imperative command surface — no `play()`, no `pause()`, no
`animation_name` yet. Animation control is the obvious next addition and it is
not in 1.0.0. Use `attributes={"autoplay": "", "animation-name": "Wave"}` in
the meantime; see [Attributes and parity](/attributes-and-parity).
