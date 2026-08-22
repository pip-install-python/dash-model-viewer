# Changelog

All notable changes to `dash-model-viewer` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [1.0.0] — 2026-08-21

A clean break. The package is rebuilt around a Dash hook; the old
`DashModelViewer` component and its generated build are gone. See **Migrating**
at the end of this entry.

### Fixed

- **WebXR AR now works out of the box on Android.** `arModes` defaulted to
  `"basic_annotations scene-viewer quick-look"`. `basic_annotations` is not an
  AR mode — it is the name of a folder in `usage_tests/`, copy-pasted into the
  default. The effect was that `webxr` was absent from the AR mode list in
  every default configuration, so the package's flagship feature had never
  worked without the user discovering and overriding the prop. The hub
  documentation has always shown the correct value, so the code and the docs
  have disagreed since the first release. The default is now
  `"webxr scene-viewer quick-look"`.

- **Events reach Python.** The `setProps` call was commented out, so the
  component had no output props at all — every interaction required a
  `clientside_callback`. Camera changes, load and progress state, AR status and
  tracking, hotspot clicks, and scene-point picking are now Dash props.

- **Event listeners no longer accumulate.** `removeEventListener` was called
  with a freshly-created closure on every render, so it removed nothing and
  listeners piled up for the lifetime of the page. Unmount cleanup removed only
  the injected script tag.

### Changed

- **`@google/model-viewer` is a real dependency, vendored at 4.3.1.** It was
  previously fetched at runtime from a hard-coded
  `ajax.googleapis.com` URL pinned to 3.5.0, injected into `document.body` by
  every component instance. That made the package unusable offline, behind a
  corporate egress proxy, or under a strict `script-src` CSP, and left the
  version outside the consumer's control. The bundle now ships in the wheel and
  is emitted by `dash.hooks.script()`. Opt back into a CDN — or point at an
  internal mirror — with `dash_model_viewer.configure(use_cdn=...)`, which must
  run before `Dash()` is constructed.

- **Hotspots are components, not dictionaries.** `hotspots=[{...}]` becomes
  `children=[Slot(...)]`. `Slot` accepts arbitrary Dash children, which the old
  list-of-dicts could not — that limitation existed only because
  `dash.html.Div` has no `slot` prop. `ar_button_text`, `custom_ar_prompt` and
  `custom_ar_failure` are absorbed into `Slot` and removed.

- **Props are `snake_case`** (`camera_controls`, not `cameraControls`).

- **Arbitrary model-viewer attributes are supported permanently.** The
  `attributes` dict and `mv_*` wildcard props pass through any attribute
  model-viewer supports — including ones added upstream after this release —
  with no regeneration and no new version of this package.

### Added

- `camera_change_debounce` (default `100` ms), a **required** guard rather than
  an optimisation. `camera-change` and `progress` fire at frame rate, so
  unthrottled two-way camera props are a callback storm; and because
  `camera_orbit` is two-way, a callback that writes it re-triggers itself. The
  shim suppresses the echo via `event.detail.source`.

### Removed

- **The build.** No `package.json`, webpack, babel, `dash-generate-components`,
  `metadata.json`, or React source. The three layers — vendored bundle,
  hand-authored shim, hand-written Python components — are each the source of
  record. A test asserts the generator stays gone, because a stale dev
  environment on dash 2.18 could otherwise regenerate the Python *backwards*.

- **R and Julia bindings** (`R/`, `man/`, `deps/`, `inst/`, `NAMESPACE`,
  `DESCRIPTION`, `Project.toml`). Generated, never used, and ~550 MB of the
  repository.

- `DashModelViewer`. The module is now `_components.py`; the old filename is
  retired so a stale copy cannot shadow the new one.

### Migrating from 0.0.1

```python
# 0.0.1
from dash_model_viewer import DashModelViewer

DashModelViewer(
    id="v", src="/assets/shoe.glb", alt="A shoe",
    cameraControls=True,
    arModes="webxr scene-viewer quick-look",   # you had to know to set this
    hotspots=[{"slot": "hotspot-1", "position": "0 1 0", "text": "Sole"}],
    arButtonText="View in your space",
)
```

```python
# 1.0.0
import dash_model_viewer as dmv
from dash import html

dmv.ModelViewer(
    id="v", src="/assets/shoe.glb", alt="A shoe",
    camera_controls=True,
    # ar_modes now defaults to "webxr scene-viewer quick-look"
    children=[
        dmv.Slot(slot="hotspot-1", position="0 1 0", children="Sole"),
        dmv.Slot(slot="ar-button", children=html.Button("View in your space")),
    ],
)
```

| 0.0.1 | 1.0.0 |
|---|---|
| `cameraControls`, `cameraOrbit`, … | `camera_controls`, `camera_orbit`, … |
| `hotspots=[{...}]` | `children=[Slot(...)]` |
| `arButtonText=` | `Slot(slot="ar-button", …)` |
| `customArPrompt=` | `Slot(slot="ar-prompt", …)` |
| `customArFailure=` | `Slot(slot="ar-failure", …)` |
| `arModes` default silently disabled WebXR | correct by default |
| clientside callbacks for every event | `camera`, `model_info`, `ar_status`, … |
| *(no equivalent)* | `attributes={...}` / `mv_*` for full upstream parity |

## [0.0.1] — 2025-05-01

Initial release.

[Unreleased]: https://github.com/pip-install-python/dash-model-viewer/compare/main...HEAD
[1.0.0]: https://github.com/pip-install-python/dash-model-viewer/releases/tag/v1.0.0
[0.0.1]: https://github.com/pip-install-python/dash-model-viewer/releases/tag/v0.0.1
</content>
