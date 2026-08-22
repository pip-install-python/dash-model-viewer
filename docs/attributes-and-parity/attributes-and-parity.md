---
name: Attributes and Parity
description: Reach every model-viewer attribute — including ones added upstream after this release — without waiting for a new version of this package.
endpoint: /attributes-and-parity
package: dash_model_viewer
icon: mdi:tune-variant
---

.. llms_copy::Attributes and Parity

.. toc::

### The problem this solves

`<model-viewer>` has roughly seventy attributes and gains more with every
release. A wrapper that hand-lists them is out of date the day upstream ships a
new one, and every addition costs a regeneration, a release, and an upgrade on
your side.

`dash-model-viewer` names about twenty of them and gives you two escape hatches
that reach **all** of the rest — including attributes that do not exist yet.

| Family | Looks like | Use it for |
| :-- | :-- | :-- |
| Named props | `camera_controls=True` | The common ones. Validated, documented, autocompleted. |
| `mv_*` wildcards | `mv_environment_image="neutral"` | Anything else, one at a time, at the call site. |
| `attributes` dict | `attributes={"exposure": "1.2"}` | Anything else, as data — from a callback, a config file, or a model. |

Precedence when the same attribute is set twice: **named prop > `mv_*` >
`attributes`**.

---

### Live

Every attribute driven by this control is one `dash-model-viewer` has no named
prop for. Nothing was regenerated to make them work.

.. exec::docs.attributes-and-parity.parity
    :code: false

.. source::docs/attributes-and-parity/parity.py

---

### `mv_*` — the ergonomic form

Python `snake_case` becomes kebab-case attributes:

```python
dmv.ModelViewer(
    id="viewer", src=..., alt=...,
    mv_environment_image="neutral",     # environment-image="neutral"
    mv_auto_rotate_delay="0",           # auto-rotate-delay="0"
    mv_disable_tap="",                  # disable-tap  (bare attribute)
)
```

Pass `""` for boolean-style attributes whose meaning is presence, not value.

---

### `attributes` — the data form

Use this when the attribute set is computed rather than typed:

```python
@callback(Output("viewer", "attributes"), Input("theme", "value"))
def relight(theme):
    return {
        "environment-image": "neutral" if theme == "light" else MOON_HDR,
        "exposure": "1.0" if theme == "light" else "1.4",
        "shadow-softness": "0.8",
    }
```

Because it is an ordinary dict, it can come from anywhere — a database, a user
preference, a JSON config, or a language model's structured output. That last
one is the interesting case: the output space of "configure this viewer" is the
entire `<model-viewer>` attribute surface, forever, with no allow-list to
maintain.

.. admonition::Removal is by absence
    :icon: radix-icons:info-circled
    :color: blue

    The shim diffs each render against the previously applied set and removes
    anything that has gone away. Returning a dict without a key you previously
    set removes that attribute — you do not need a sentinel value. It also
    means the shim never re-writes an attribute that has not changed, so
    `model-viewer` is never interrupted mid-animation.

---

### When to ask for a named prop instead

The escape hatches are complete, not equal. A named prop earns its place when
the attribute:

- needs validation (a typo in `attributes` is silent — the browser ignores
  unknown attributes);
- has a non-obvious default worth documenting;
- is two-way, like `camera_orbit`;
- or needs a Python-side type that is not a string.

If you find yourself writing the same `attributes` entry in every project,
that is a good argument for a named prop —
[open an issue](https://github.com/pip-install-python/dash-model-viewer/issues).

---

### The full attribute list

Upstream, and always current:
[modelviewer.dev/docs](https://modelviewer.dev/docs/). This package vendors
`model-viewer` **4.3.1**; `dmv.MODEL_VIEWER_VERSION` reports it at runtime, so
you can check the docs against what you are actually running.
