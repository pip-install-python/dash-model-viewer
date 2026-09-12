# Changelog

All notable changes to `dash-model-viewer` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet. 1.0.0 has not been published — PyPI still serves 0.0.1 — so the
pre-release component review's changes are recorded under `[1.0.0]` below
rather than here. Once 1.0.0 is tagged, anything further belongs in this
section.

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

- **`src` and `alt` are enforced, not merely documented.** The docstring,
  `api_metadata.json` and the API reference had all called them required while
  nothing checked — `ModelViewer()` with neither constructed silently. Omitting
  either now raises the standard Dash `TypeError` naming the prop, and an
  explicit `None` fails the same way. `alt` is the entire experience for a
  screen-reader user; a wrapper that lets you forget it makes the inaccessible
  case the easy one. 0.0.1's generated metadata declared `id`/`src`/`alt`
  required, so this restores two of the three; `id` stays optional, because a
  viewer with no callbacks needs none.

- **A picking example.** `pick_on_click` and `scene_point` were documented from
  the start and demonstrated nowhere, so nothing would have noticed if the
  shim's click path broke. `/events-and-callbacks` now runs one.

- **`examples/manual_walk.py`** — a standalone app, dependent on `dash` and this
  package alone, covering the eight props no documentation page exercises
  (`poster`, `class_name` on both components, the four camera bounds,
  `touch_action`) and a viewer whose `src` 404s, so `model_state`'s error
  payload can be observed rather than merely wired.

- **A release lane.** `.github/workflows/release.yml`: a `v*` tag verifies that
  the tag matches `pyproject`'s version and that the CHANGELOG documents it,
  builds, runs the package's own suites against the built wheel, asserts the
  wheel carries the vendored runtime, then publishes to PyPI by OIDC trusted
  publishing with no stored token. The wheel-content gate is the one that
  matters here: the JavaScript is committed rather than built, so a wheel
  missing `vendor/model-viewer-umd.min.js` would be dead on arrival and a
  version cannot be re-uploaded to replace it.

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

- **Provider keys from the deployed site.** The documentation host carries no
  `ANTHROPIC_API_KEY` and no `CHATGPT_API_KEY` (owner's decision,
  2026-09-12): the sites are documentation and do no production spend. The
  generative pages therefore ship an empty model picker, a disabled generate
  control and a line explaining why, on every deployment. That is the expected
  production state rather than a misconfiguration, and it is said on the pages
  so nobody files it as a bug. Run the site locally with a `.env` to use them;
  `lib/spend.py`'s rolling call limit and dollar ceiling then apply there.

- **`camera["source"]`.** The shim reports camera movement only for user
  interaction — that is the echo suppression above — so the key could only ever
  hold the single string `"user-interaction"`. A field with one possible value
  tells a reader nothing and implies another value is reachable. The payload is
  `{"orbit", "target", "field_of_view"}`. The suppression is unchanged.

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
