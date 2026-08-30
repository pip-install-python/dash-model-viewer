---
name: API Reference
description: Every prop on ModelViewer and Slot, every event payload, and the precedence rules.
endpoint: /api-reference
category: Reference
order: 1
package: dash_model_viewer
icon: mdi:code-braces
lastmod: 2026-08-08
---

.. llms_copy::API Reference

.. toc::

### `dmv.ModelViewer`

#### Required

| Prop | Type | Notes |
| :-- | :-- | :-- |
| `src` | `str` | URL of the `.glb` / `.gltf`. Relative paths resolve against `assets/`. |
| `alt` | `str` | Accessible description. Not decorative — it is the entire experience for a screen-reader user. |

#### Layout

| Prop | Type | Default | Notes |
| :-- | :-- | :-- | :-- |
| `id` | `str \| dict` | — | Callback id. Pattern-matching dicts work. |
| `style` | `dict` | — | **Give it a height.** The element has no intrinsic size. |
| `class_name` | `str` | — | CSS class on the viewer element. |
| `children` | list of `Slot` | — | Hotspots, AR button, poster, progress bar. |

#### Camera

| Prop | Type | Default | Notes |
| :-- | :-- | :-- | :-- |
| `camera_controls` | `bool` | `True` | Orbit, zoom, pan. |
| `touch_action` | `'pan-y' \| 'pan-x' \| 'none'` | `'pan-y'` | Which gestures the page keeps. |
| `camera_orbit` | `str` | — | `"theta phi radius"`. Two-way. |
| `camera_target` | `str` | — | `"X Y Z"` in metres. |
| `field_of_view` | `str` | — | e.g. `"30deg"`. |
| `min_field_of_view` / `max_field_of_view` | `str` | — | Zoom limits. |
| `min_camera_orbit` / `max_camera_orbit` | `str` | — | `"auto auto auto"` for none. |
| `interpolation_decay` | `float` | — | Camera easing. Lower is slower; `0` is a jump cut. |
| `camera_change_debounce` | `float` | `100` | Milliseconds. **Do not set to 0 without meaning it.** |

#### Rendering

| Prop | Type | Default |
| :-- | :-- | :-- |
| `poster` | `str` | — |
| `tone_mapping` | `str` | `'neutral'` |
| `shadow_intensity` | `float` | — |
| `variant_name` | `str \| None` | `None` |

#### Augmented reality

| Prop | Type | Default |
| :-- | :-- | :-- |
| `ar` | `bool` | `True` |
| `ar_modes` | `str` | `'webxr scene-viewer quick-look'` |
| `ar_scale` | `'auto' \| 'fixed'` | `'auto'` |

#### Escape hatches

| Prop | Type | Notes |
| :-- | :-- | :-- |
| `attributes` | `dict[str, str]` | Raw kebab-case attributes. |
| `mv_*` | `str` | Wildcard. `mv_environment_image` → `environment-image`. |

Precedence: **named prop > `mv_*` > `attributes`**.

#### Read-only (set by the component)

| Prop | Payload |
| :-- | :-- |
| `camera` | `{"orbit": str, "target": str, "field_of_view": str, "source": str}` — only for user interaction |
| `model_state` | `{"status": "loading" \| "loaded" \| "error", "progress": float, "detail": str?}` |
| `model_info` | `{"dimensions": {"x": float, "y": float, "z": float}, "variants": [str], "animations": [str]}` |
| `ar_status` | `"not-presenting" \| "session-started" \| "object-placed" \| "failed"` |
| `ar_tracking` | `"tracking" \| "not-tracking"` |
| `scene_point` | `{"position": str, "normal": str, "uv": [float, float]}` or `None` |

#### Input-only

| Prop | Type | Default | Notes |
| :-- | :-- | :-- | :-- |
| `pick_on_click` | `bool` | `False` | Arms `scene_point`. |

---

### `dmv.Slot`

| Prop | Type | Default | Notes |
| :-- | :-- | :-- | :-- |
| `slot` | `str` | — | **Required.** `"hotspot-*"`, `"ar-button"`, `"ar-prompt"`, `"ar-failure"`, `"poster"`, `"progress-bar"`. |
| `children` | components | — | Any Dash component. |
| `position` | `str` | — | `"X Y Z"` in model space. Required for hotspots. |
| `normal` | `str` | — | `"X Y Z"` surface normal; drives occlusion. |
| `id` | `str \| dict` | — | Callback id. |
| `style` | `dict` | — | |
| `class_name` | `str` | — | Added alongside the built-in `dmv-slot`. |
| `n_clicks` | `int` | `0` | Increments on click. Use as an `Input`. |

---

### Module level

| Name | Type | Notes |
| :-- | :-- | :-- |
| `dmv.__version__` | `str` | Read from installed metadata, not from a bundled JSON file. |
| `dmv.MODEL_VIEWER_VERSION` | `str` | The vendored `<model-viewer>` version — `"4.3.1"`. |
| `dmv.DEFAULT_AR_MODES` | `str` | `"webxr scene-viewer quick-look"`. |
| `dmv.DEFAULT_CAMERA_CHANGE_DEBOUNCE` | `int` | `100`. |
| `dmv.configure(use_cdn=...)` | function | See below. |

#### `configure(use_cdn=False)`

```python
dmv.configure(use_cdn=False)                        # default: vendored (in-wheel)
dmv.configure(use_cdn=True)                         # public jsDelivr, pinned version
dmv.configure(use_cdn="https://cdn.example/mv.js")  # your own mirror
```

Must run **before the first request is served**. Dash reads the hook's resource
list while generating the index page, so a call from inside a callback or a
lazily-imported page module may or may not take effect. Put it at module scope.

---

### Not in 1.0.0

Stated so you do not go looking:

- **Animation playback props.** Use `attributes={"autoplay": "", "animation-name": ...}`.
- **Imperative methods** — no `play()`, `pause()`, or programmatic `activateAR()`.
- **`ios_src` as a named prop.** Use `mv_ios_src`.
- **Annotation/label auto-layout.** `Slot` positions are yours to compute.
