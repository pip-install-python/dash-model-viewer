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

- **A generated sculpture's manifest was refused by its own importer, and the
  page said nothing.** `lib/sculptor` CLAMPED every field while building —
  emissive strength to 0–1, roughness to 0.05–1.0, size and position to their
  bounds, and it accepted a colour written without its `#` — while
  `manifest.from_scene` stored the model's RAW values, which `lib/manifest`
  then refused. A sculpture containing a flame at `emissive_strength: 3.0` (a
  value the system prompt's own worked example used) drew perfectly and
  produced a manifest every consumer of the store rejected. **One swallowed
  `ManifestError` produced three unrelated-looking symptoms**: the texture
  switch fell back to the untextured render *under a note reading "Draped on
  screen only"*, the `.glb` button did nothing, and the manifest button did
  nothing. The clamps now live in exactly one place — `sculptor.normalise_part`
  — which the builder reads its numbers from and which `from_scene` stores, so
  a stored manifest is valid by construction; a test renders both paths and
  compares bytes for every out-of-range value a model can emit. And nothing is
  swallowed: a refused render or download now shows the importer's own message,
  naming the field and the bound it broke, instead of returning `no_update`
  (which is indistinguishable from a button that does nothing). The same
  surfacing is applied to [Generative 3D](/generative-3d), which had the
  identical silence.

- **A stale tab no longer polls a 500 for ever.** Observed on this host: a tab
  left open on `/sculpt-from-image` across a restart posted a callback id the
  running server no longer had, and Dash answered `500` to every tick — at
  700 ms, indefinitely, behind a spinner that never stopped. It read as a hung
  build. The cause was benign (the tab predated the commit that widened that
  callback's output list, and Dash's callback id hashes only the INPUTS, so its
  `@hash` matched while the output list did not); the consequence was not,
  because every deploy that changes a callback's outputs puts every open tab in
  that state. Both generating pages now bound the timer with `max_intervals`,
  derived from the progress store's TTL rather than chosen, and carry a
  CLIENTSIDE stale guard — the server writes the tick it last answered on, and
  the browser says "This page is out of date — reload it" and stops the timer
  after five ticks of silence. Clientside because it has to run in exactly the
  state where server callbacks cannot. It cannot rescue a tab older than
  itself; what it prevents is the next deploy doing it again. New in
  `lib/poll_guard.py`.

- **`/generative-3d` recorded the wrong provenance in every file it exported.**
  Its poll declared `State("g3-model")` then `State("g3-prompt")` and received
  them transposed, so each saved manifest carried the model id under `prompt`
  and the prompt text under `model`. The sculpture was unaffected; only the
  record of how it was made was wrong — the half a file keeps after the session
  is gone. The suite missed it because the tests called the function in ITS
  parameter order rather than through the wiring, which cancelled the
  transposition out. `tests/test_callback_wiring.py` now compares every
  callback's parameter order against the order Dash wires into it, and flags a
  parameter that matches a DIFFERENT dependency of the same callback — a rule
  that fires on one of this app's 43 callbacks and fired on this bug.

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

- **A prompt-version axis on [Benchmark](/benchmark).** The page's fourth
  axis varies *this site's own instructions* rather than the model's settings:
  **v1**, which every other page uses, against **v2**, which teaches the model
  scene-manifest version 2 and adds one further instruction — that parts may
  and should interpenetrate where they join, because a lamp sits *into* the top
  of its tower rather than balancing on it. Every other setting is held, so a
  difference is attributable to the prompt. Each result panel now carries the
  number that claim turns into: of the part pairs close enough to read as
  joined, how many actually **blend** rather than merely touching — computed
  from the returned manifest by geometry alone, with no rendering and no second
  call. **v2 is the default nowhere.** Its whole claim is that it produces
  better sculptures, and only model runs can show that, so it runs here and
  nowhere else until a sweep earns the promotion; a test fails if any page that
  generates sculptures ever selects it.

- **Scene manifest version 2 — define a thing once and place it.** Three
  additive entries: a `defs` block naming sub-assemblies, a `ref` that places
  one, and a `group` that gathers parts under a shared transform. Nesting is
  allowed to four levels; the 28-part ceiling now counts LEAVES after
  expansion, because a `ref` costs its def's part count every time it is
  placed. A def deliberately has no `position` — it describes a thing, a `ref`
  says where a copy goes — so a ref cannot restyle or resize what it places and
  every placement provably shares **one mesh and one material**. The bundled
  `cart.json` draws 8 parts from 4 entries in 4 meshes and is **69% smaller**
  than `cart-flat.json`, the same sculpture placed by hand; a test asserts the
  two put every node in exactly the same position and rotation. Rotations
  compose as quaternions rather than by adding Euler angles, which do not add.
  **Version 1 is unaffected**, asserted by SHA-256 on the three original
  samples. The exported `.glb` remains a flat scene — shared meshes, one node
  per part — so the two shipped readers that assume a mesh's transform is its
  world transform (`lib/overlap.py`, `lib/texture.py`) keep working; a test
  asserts neither can tell the nested cart from the flat one. Making the
  authored grouping survive export is a later, separate change.

- **[Model Upload](/model-upload) — render your own `.glb`.** Every other page
  hands `<model-viewer>` a model this site chose; this one takes a `dcc.Upload`
  and renders the visitor's file, beside a readout of what is actually in it:
  nodes, meshes, triangles, materials, textures, animation clips and the
  extensions it declares. The file is identified by its CONTENT rather than the
  media type the browser guessed — a `.glb` is recognised by its magic number
  and version field, and its declared length is checked against the bytes
  received, so a truncated transfer is named instead of failing silently in the
  viewer. A `.gltf` JSON file is refused with the reason it cannot work: it
  points at buffers and textures that were not uploaded with it. Reading is
  header-and-JSON-chunk only, so describing a 30 MB model costs what describing
  a 30 KB one costs. Rules live in `lib/uploads.py` beside the image ones; the
  reader is `lib/glb.summarize()`.

- **Drape the uploaded image over the sculpture it produced.**
  [Sculpt from an Image](/sculpt-from-image) gains a three-state texture
  switch: **Off** (the generated colours), **Preview** (draped on screen, the
  `.glb` still downloads plain, and the button relabels itself to say so) and
  **Include** (baked into the download as `…-textured.glb`). The UVs are a
  front planar projection computed from *world* position after the parts are
  placed, so the parts together carry one picture rather than each wearing its
  own copy — the unit-square-per-primitive alternative is what makes a
  28-part sculpture look like 28 small photographs. Draped parts take a white
  base colour, go fully non-metallic and take a roughness floor — glTF
  multiplies base colour into the texture, and in metallic-roughness PBR the
  diffuse term is `baseColor x (1 - metallic)`, so a part left at the
  `metallic: 0.9` the prompt asks for on anything gold or polished showed
  almost none of the picture. `emissive` is deliberately left alone, because it
  adds light rather than replacing albedo, so a glowing part still glows. Switching back to
  Off is byte-identical to never having textured. The manifest stays
  textureless — draping happens at render time — so a saved manifest is the
  same file either way, and the whole switch works on a host with **no API
  key**: a bundled sample plus an uploaded picture bakes and downloads. New in
  `lib/texture.py`; embedded images are now deduplicated by content in
  `lib/glb.py`, without which a realistic 800 KB photograph across 28 parts
  would come to ~23 MB against the 3 MB ceiling.

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

- **An animation page.** `/animation` plays a model's built-in clips, switches
  between them with a crossfade and pauses — with the clip list read from
  `model_info["animations"]` rather than hardcoded, so it works for any
  animated model. Entirely through the `attributes` escape hatch, since 1.0.0
  ships no imperative surface; the page states what that rules out (`currentTime`
  and `timeScale` have no attribute equivalent, so no scrubbing and no speed
  control) rather than leaving anyone hunting for a prop.

- **An attribute tour.** `/attribute-tour` drives the eleven `<model-viewer>`
  attributes that have no named prop — `scale`, `loading`, `reveal`,
  `disable-pan`, `disable-tap`, `interaction-prompt`, `skybox-image`,
  `skybox-height` — and documents the three only a phone can show.
  `ar-placement` and `xr-environment` are set on `/augmented-reality` instead,
  where a device walk can verify them; `ios-src` stays documentation-only
  because Quick Look needs a `.usdz` this repo does not ship, and pointing it
  at a missing file would break iOS AR in order to document an attribute. The
  page remounts its viewer on every change, because `loading` and `reveal` do
  nothing to a model that has already loaded. Written from an audit against
  modelviewer.dev's own examples; `effects` and the postprocessing page are
  deliberately out of scope, needing a separate ES-module addon that the
  classic-script rule in `.claude/ARCHITECTURE.md` forbids.

- **A scene manifest you can export, edit and re-render.** The JSON a
  generated sculpture is made of is now a documented, versioned format
  (`/scene-manifest`) with an importer, a byte-stable exporter and a `.glb`
  download on both generating pages. `lib/glb.py` is deterministic, so a
  manifest re-renders byte-identically — which makes the file a way back to the
  object rather than a souvenir, and means editing a sculpture costs nothing
  where asking a model to change it costs a call. `provenance` records the
  prompt, model, cost and date and is never read by the renderer. Nothing is
  written to disk: imports are validated in memory and refused with the field's
  path named, and downloads are bytes handed straight to the response. The
  round trip works on a host with **no API key at all** — three committed
  sample manifests demonstrate it, one of them at exactly the 28-part limit.

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
