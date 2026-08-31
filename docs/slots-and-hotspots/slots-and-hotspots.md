---
name: Slots and Hotspots
nav: Slots
description: Anchor any Dash component to a point on the model — and why hotspots used to be a list of dictionaries.
endpoint: /slots-and-hotspots
category: Viewing
order: 3
package: dash_model_viewer
icon: mdi:map-marker-radius-outline
lastmod: 2026-08-08
---

.. llms_copy::Slots and Hotspots

.. toc::

### Anchored labels

A hotspot is a `Slot` whose name begins with `hotspot-` and which carries a
`position` in model space. `<model-viewer>` projects it onto the model, keeps
it attached as the camera moves, and hides it when the geometry occludes it.

.. exec::docs.slots-and-hotspots.hotspots
    :code: false

.. source::docs/slots-and-hotspots/hotspots.py

The children are a real `dmc.Badge`. Not a string, not a class name, not a
config dict — an actual Dash component, with all of its props.

---

### Why this was a list of dictionaries

In 0.0.1 hotspots looked like this:

```python
DashModelViewer(
    hotspots=[
        {"slot": "hotspot-visor", "position": "0 1.75 0.35",
         "text": "Visor", "children_classname": "label"},
    ],
)
```

Content was limited to a `text` string and a CSS class. That was not a design
choice — it was a workaround.

`<model-viewer>` places its extras into named shadow-DOM slots, which requires
a child element carrying a `slot` attribute. **`dash.html.Div` has no `slot`
prop**, and neither does any other core Dash component. There was no way to put
an arbitrary Dash component into a slot, so the component rendered its own
plain `<div>`s from a serialisable description of them, and the description was
the only thing a user could reach.

`Slot` is a component that *does* have `slot`. Everything downstream follows —
arbitrary children, real callbacks, `n_clicks`.

---

### Every slot, not just hotspots

`Slot` is the general mechanism. The AR button, the AR prompt, the failure
message, the poster and the progress bar are all just named slots, so the three
separate props 0.0.1 had for them (`arButtonText`, `customArPrompt`,
`customArFailure`) collapse into one component:

```python
dmv.ModelViewer(
    id="viewer", src=..., alt=...,
    children=[
        dmv.Slot(slot="ar-button",  children=dmc.Button("View in your space")),
        dmv.Slot(slot="ar-prompt",  children=dmc.Loader(size="sm")),
        dmv.Slot(slot="ar-failure", children=dmc.Alert("AR lost tracking", color="red")),
        dmv.Slot(slot="poster",     children=html.Img(src="/assets/poster.webp")),
        dmv.Slot(slot="progress-bar", children=html.Div(className="my-bar")),
    ],
)
```

The full list of slot names is in
[model-viewer's own documentation](https://modelviewer.dev/docs/#loading-slots).

---

### `n_clicks` is the point

Each `Slot` has its own `n_clicks`, so a hotspot is a callback `Input` like any
button:

```python
@callback(Output("viewer", "camera_orbit"), Input("sh-visor", "n_clicks"))
def look_at_visor(_):
    return "0deg 70deg 1.2m"
```

For many hotspots, use pattern-matching ids — see
[Camera and views](/camera-and-views), which drives four presets from one
callback.

---

### Styling

Slots render with the class `dmv-slot`, plus anything you pass as `class_name`.
They are ordinary DOM, so ordinary CSS reaches them:

```css
.dmv-slot {
    --min-hotspot-opacity: 0;      /* fade out when occluded */
}

.dmv-slot[slot^="hotspot-"] {
    background: rgba(0, 0, 0, .65);
    border-radius: 999px;
    padding: 4px 10px;
    color: white;
    cursor: pointer;
}
```

.. admonition::Positions are in model space, not world space
    :icon: radix-icons:info-circled
    :color: blue

    `position="0 1.75 0.35"` is metres in the model's own coordinate system, so
    the numbers that work for one model are meaningless for another. To place
    hotspots on a model you have not measured, set `pick_on_click=True` and read
    the coordinates back from `scene_point` — see
    [Events and callbacks](/events-and-callbacks).
