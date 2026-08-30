---
name: Model Switching and Variants
description: Swap the model at runtime, and drive GLTF material variants from a dropdown the viewer populates itself.
endpoint: /model-switching
category: Viewing
order: 2
package: dash_model_viewer
icon: mdi:swap-horizontal
lastmod: 2026-08-08
---

.. llms_copy::Model Switching and Variants

.. toc::

### Swapping models

`src` is an ordinary prop. Change it from a callback and the viewer loads the
new file, keeping the camera where the user left it.

.. exec::docs.model-switching.switching
    :code: false

.. source::docs/model-switching/switching.py

---

### Variants populate themselves

The interesting part is the second callback. The variant dropdown is **not**
hard-coded — it is filled from `model_info["variants"]`, which the viewer
reports after the file loads.

```python
@callback(
    Output("ms-variant", "data"),
    Input("ms-viewer", "model_info"),
)
def list_variants(info):
    return (info or {}).get("variants") or []
```

Switch to the Astronaut and the dropdown empties, because that file has no
variants. Switch back to the Shoe and its three return. Nothing on the server
knows anything about either file.

This is the shape of every "user uploads their own model" feature, and it was
not possible in 0.0.1 — the variant list lived in the browser and there was no
way to get it out.

---

### `variant_name`

| Value | Effect |
| :-- | :-- |
| `None` | The GLTF's default variant. |
| `"default"` | Also the default — accepted for readability. |
| `"Midnight"` | That named variant, if present. |

An unknown name is ignored by `<model-viewer>` rather than raising, so validate
against `model_info["variants"]` if it matters.

---

### Loading state during a swap

A large model swap is not instant, and an unstyled viewer shows the *old* model
until the new one is ready. Use `model_state` to say so:

```python
@callback(Output("overlay", "style"), Input("viewer", "model_state"))
def spinner(state):
    loading = (state or {}).get("status") == "loading"
    return {"display": "flex" if loading else "none"}
```

A `poster` image is the cheaper version of the same idea — it covers the first
load, though not subsequent swaps:

```python
dmv.ModelViewer(..., poster="/assets/preview.webp")
```

.. admonition::Cache-bust deliberately, or not at all
    :icon: radix-icons:info-circled
    :color: blue

    `src` is a URL, so the browser caches it. If your models are user-uploaded
    and can change at the same URL, append a version or hash — otherwise a
    re-upload shows the previous mesh and looks like the upload failed.

---

### Animations

`model_info["animations"]` lists the clips in the file. Playback control is not
a named prop in 1.0.0; drive it through
[attributes](/attributes-and-parity) meanwhile:

```python
@callback(Output("viewer", "attributes"), Input("clip", "value"))
def play(clip):
    return {"autoplay": "", "animation-name": clip}
```
