# dash-model-viewer 1.0.0 — architecture, verified

Status: **built**. Written 2026-08-08 as a specification, against Dash
**4.4.1** (`pip-docs+/.venv`) and `@google/model-viewer` **4.3.1** (npm
`latest`); the three layers below shipped in the 1.0.0 rebuild commit and the
documentation site was written against them. Read it now as the design record
and the reasoning behind each decision — not as a plan.

Everything below marked ✅ was read out of source or the network today, not
recalled. Everything marked ⚠️ corrects a claim in
`pip-docs+/kickoff/KICKOFF-modelviewer.md` or `subdomain_blueprint/REVIVAL.md`.

---

## 1. Why the rebuild (the argument that actually holds)

The kickoff justifies the rebuild with "no layer is generated". True, but that
is a maintenance preference. The argument that survives a sceptic is the
**runtime dependency**:

`@google/model-viewer` is not a dependency of this package at all. It is a
hard-coded CDN URL that every component instance injects into `document.body`
at mount time — `src/lib/components/DashModelViewer.react.js:68,81`, pinned to
**3.5.0** against an upstream of **4.3.1**. ✅

That single line costs the package five separate things:

| Consequence | Who it breaks |
|---|---|
| No offline / air-gapped operation | Every enterprise install |
| Blocked by a strict `script-src` CSP | Any site with a real CSP |
| Blocked behind a corporate egress proxy | Most large deployments |
| Consumer cannot pin or override the version | Everyone, permanently |
| Silent version drift from `pip install` | Reproducible builds |

Vendoring the bundle and emitting it through `dash.hooks.script()` fixes a
**supply-chain and deployability** defect. "The bundle is the source" is the
pleasant side effect, not the reason.

The second defect — `arModes` defaulting to `"basic_annotations scene-viewer
quick-look"` (`DashModelViewer.react.js:33`, present in committed upstream ✅) —
means WebXR has never been in the default AR mode list, so the flagship feature
has never worked out of the box on Android. That is the CHANGELOG headline.

---

## 2. The three layers

A hook cannot render. `hooks.script()` appends to a list
(`dash/_hooks.py:180-182`) ✅ — it has no layout surface. So the package is
three hand-authored layers and **zero generated ones**:

```
L1  dash_model_viewer/vendor/model-viewer-umd.min.js   Google's UMD build, 4.3.1, verbatim
      ↑ emitted by  dash.hooks.script([...])  at import time
L2  dash_model_viewer/dash_model_viewer.js             hand-authored shim, no build step
      ↑ reads window.React, registers the Dash component namespace
L3  dash_model_viewer/_components.py                   hand-written Component subclasses
```

No `package.json`, no webpack, no babel, no `dash-generate-components`, no
`metadata.json`, no React source, no `npm install`. The `R/`, `man/`, `deps/`,
`inst/`, `NAMESPACE`, `DESCRIPTION`, `Project.toml` bindings are deleted
(generated, never used, and `deps/` + `inst/` alone are 278 MB each ✅).

---

## 3. ⚠️ The script-timing argument — correct conclusion, wrong stated mechanism

REVIVAL.md §2 says a UMD build "executes synchronously in document order, so
`customElements.get(...)` is already defined **before Dash mounts**". The
conclusion is right. The mechanism implied — that hook scripts precede the Dash
renderer — is **not** what Dash 4.4.1 does, and the difference matters because
it is five lines away from being "optimized" by someone tidying `dash.py`.

What actually happens (`dash/dash.py`, `_generate_scripts_html`, ~L1306-1336) ✅:

```
srcs = [ React, ReactDOM ]                 # _dash_renderer._js_dist_dependencies
      + config.external_scripts
      + [ assets, dash-renderer bundle, dcc, html, dash_table,
          hooks._js_dist ]                 # ← hook scripts are appended LAST
```

Hook scripts land **after** the dash-renderer bundle, not before it. The race is
still won, for a different reason — the default index template
(`dash/dash.py:96`) ✅ is:

```html
<footer>
    {%config%}
    {%scripts%}     ← every <script src>, hook scripts last
    {%renderer%}    ← inline: var renderer = new DashRenderer(...)   (dash.py:635)
</footer>
```

`{%renderer%}` is the inline statement that actually *mounts* the app. A
**classic** script in `{%scripts%}` executes before the parser reaches
`{%renderer%}`, so the custom element is defined before mount. A
`type="module"` script is deferred until after document parse — i.e. after
`new DashRenderer(...)` has already run — and the race returns.

**Therefore:**

- Use `dist/model-viewer-umd.min.js`, never `dist/model-viewer.min.js`.
- Never set `attributes: {"type": "module"}` on the hook resource.
- Never set `"async"` on the hook resource — `ResourceType` accepts
  `async: bool | "eager" | "lazy"` (`dash/resources.py:14-30`) ✅ and any of
  them reintroduces the race.

A test must assert all three, because none of them fail loudly — they fail as an
intermittent "sometimes the model doesn't render".

---

## 4. How the vendored bundle is served ✅

`hooks.script()` takes `List[ResourceType]` (`dash/_hooks.py:180`). The relevant
keys (`dash/resources.py:14-30`):

```python
from dash import hooks

hooks.script([{
    "namespace": "dash_model_viewer",
    "relative_package_path": "vendor/model-viewer-umd.min.js",
}])
```

`Dash._collect_and_register_resources` resolves that by:

1. `importlib.import_module("dash_model_viewer").__version__` — so
   **`__version__` must be a real module attribute**, or index generation raises.
2. `sys.modules["dash_model_viewer"].__file__` + the relative path, `os.stat` for
   `st_mtime` → cache-busting fingerprint.
3. `self.registered_paths["dash_model_viewer"].add(rel_path)` — self-registering,
   so serving does **not** depend on a component ever being instantiated.
4. Serves at `/_dash-component-suites/dash_model_viewer/<fingerprint>`.

Two consequences worth writing down:

- The hook works even if the user never puts a `ModelViewer` in their layout.
  Importing the package is enough. That is the intended behaviour, and it is
  also why `configure()` (below) must run **before** `Dash()` is constructed.
- `__version__` is read from **installed metadata**
  (`importlib.metadata.version("dash-model-viewer")`), *not* from a JSON file.
  `2plot_leaflet/dash_leaflet2/__init__.py` reads `package-info.json` at import
  time; we deliberately do not, because a stray `package-info.json` is one of
  the artefacts the anti-regeneration test forbids (REVIVAL §1c).

### CDN escape hatch

```python
import dash_model_viewer as dmv
dmv.configure(use_cdn=True)          # or use_cdn="https://internal.example/mv.js"
```

Swaps the resource for `{"external_url": ...}`. Must be called before `Dash()`,
because `hooks.script()` state is read during index generation. Document that
constraint loudly; it is the kind of thing that works in dev and fails in
gunicorn with `--preload`.

---

## 5. ⚠️ Bundle weight — a real cost, stated honestly

`@google/model-viewer@4.3.1/dist/model-viewer-umd.min.js` is **1,071,671 bytes**
(~1.05 MB) minified ✅. It is loaded eagerly, synchronously, on every page that
imports the package — that is the price of winning the timing race.

Also present in the same dist ✅:

| File | Size |
|---|---|
| `model-viewer-umd.min.js` | 1,071,671 |
| `model-viewer-module-umd.min.js` | 483,731 |

The `-module` variant is less than half the size. **Do not adopt it on the
strength of that number alone** — verify what it excludes (upstream ships it for
consumers who already provide three.js) before treating it as an option. Filed
as an open question, not a plan.

Repo cost: ~1 MB permanent growth, matching REVIVAL §3's 1–2 MB budget. Commit
it in a release-prep commit, not incidentally.

---

## 6. Public API (1.0.0)

Naming is **snake_case** throughout. This is a clean break; the kickoff already
names `camera_change_debounce` in snake_case, so the convention is settled.

### `ModelViewer`

Three prop families, deliberately:

**a. Named props** — the ~12 attributes that carry real semantics, get real
validation, and appear in the docs table:

```
id, src, alt, style, class_name, children,
camera_controls, touch_action, camera_orbit, camera_target,
field_of_view, min_field_of_view, max_field_of_view,
min_camera_orbit, max_camera_orbit, interpolation_decay,
poster, ar, ar_modes, ar_scale, tone_mapping, shadow_intensity,
variant_name, camera_change_debounce
```

**b. `attributes: dict`** — permanent upstream parity. Every attribute
model-viewer has ever added or will ever add works with no regeneration and no
release. This is the single most valuable decision in the rebuild and the docs
should lead with it:

```python
dmv.ModelViewer(
    id="v", src="/assets/shoe.glb", alt="A shoe",
    attributes={"environment-image": "neutral", "exposure": "1.2",
                "auto-rotate-delay": "0", "orientation": "0deg 0deg 15deg"},
)
```

**c. `mv_*` wildcard props** — the ergonomic twin of (b). `mv_environment_image`
→ `environment-image`. Same reach, nicer at the call site, no dict literal.

Precedence, and it must be tested: **named prop > `mv_*` > `attributes`**.

### `Slot`

Hotspots stop being a list-of-dicts. They were only ever a list-of-dicts because
`dash.html.Div` has no `slot` prop, so there was no way to put arbitrary Dash
children inside the custom element's shadow slots.

```python
dmv.ModelViewer(
    id="v", src="/assets/astronaut.glb", alt="An astronaut",
    children=[
        dmv.Slot(
            slot="hotspot-helmet",
            position="0 1.75 0.35", normal="0 0 1",
            children=dmc.Badge("Helmet", color="blue"),   # any Dash component
        ),
        dmv.Slot(slot="ar-button", children=dmc.Button("View in your space")),
        dmv.Slot(slot="progress-bar", children=html.Div(className="bar")),
    ],
)
```

`Slot` is the general mechanism: `ar-button`, `ar-prompt`, `ar-failure`,
`poster`, `progress-bar` and every `hotspot-*` are all just named slots. The old
`ar_button_text` / `custom_ar_prompt` / `custom_ar_failure` props collapse into
it. That is a genuine simplification, not a rename.

### Output props (new — none of these exist in 0.0.1)

This is the half of the component that has never worked. `setProps` is commented
out at `DashModelViewer.react.js:146` ✅, so there are no outputs at all, which
is why the hub's `camera_views_example.py` is 231 lines of clientside callback.

| Prop | Fires on | Shape |
|---|---|---|
| `camera` | `camera-change`, debounced | `{"orbit": str, "target": str, "field_of_view": str, "source": str}` |
| `model_state` | `load`, `error`, `progress` | `{"status": "loading"\|"loaded"\|"error", "progress": float}` |
| `model_info` | `load` | `{"dimensions": {...}, "variants": [...], "animations": [...]}` |
| `ar_status` | `ar-status` | `str` — `session-started`, `object-placed`, `failed`, … |
| `ar_tracking` | `ar-tracking` | `str` — `tracking`, `not-tracking` |
| `scene_point` | click, when `pick_on_click=True` | `{"position": str, "normal": str, "uv": [...]}` |

Two changes made while implementing this, both simplifications:

- **`hotspot_click` on `ModelViewer` became `n_clicks` on `Slot`.** A per-slot
  counter is the Dash-idiomatic shape — `Input("hotspot-sole", "n_clicks")`
  works, and pattern-matching IDs cover the "which one fired" case without a
  second prop. One less concept.
- **`request_scene_point` became a `pick_on_click` boolean.** Picking needs a
  click coordinate, so a request-style prop had nowhere to get one from. The
  boolean arms the existing click handler instead.

`model_info` is the one that deletes the most user code — model dimensions and
the GLTF variant list are the two things every non-trivial example was reaching
into JS to get.

### `camera_change_debounce` — mandatory, not optional

`camera-change` and `progress` fire at frame rate. Two independent hazards:

1. **Callback storm.** Unthrottled, a 60 Hz event stream becomes 60 server
   round-trips per second per viewer.
2. **Infinite loop.** `camera_orbit` is two-way. A callback that writes
   `camera_orbit` triggers `camera-change`, which writes `camera`, which
   re-triggers the callback. The shim must suppress echo by checking
   `event.detail.source` — model-viewer reports `"user-interaction"` vs
   `"none"`/programmatic — and drop non-user events.

Default: `camera_change_debounce=100` (ms). `0` is permitted and documented as
"you are asking for the storm". Both the debounce and the echo suppression need
a test; neither fails loudly.

---

## 7. Structural guards against regenerating backwards

The local `dash_model_viewer/DashModelViewer.py` was regenerated under dash
2.18.2 and is *older in style* than the published 0.0.1. "Remember not to run
the build" is not a guard. The real ones (REVIVAL §1c), all asserted by
`tests/test_no_regeneration.py`:

- No `package.json` anywhere in the repo.
- No file containing the string `AUTO GENERATED FILE - DO NOT EDIT`.
- No `metadata.json`, no `package-info.json`.
- The filename `DashModelViewer.py` does not exist — the module is
  `_components.py`, so a stale copy cannot shadow anything.
- `dash_model_viewer.__version__ == importlib.metadata.version("dash-model-viewer")`.

Plus the timing guards from §3:

- The hook resource has no `type` attribute and no `async` key.
- The vendored filename ends `-umd.min.js`.

---

## 8. Open questions (owner decisions, not blockers)

1. **`model-viewer-module-umd.min.js`** — 484 KB vs 1.05 MB. Verify what it
   drops before adopting. §5.
2. **A `__getattr__` shim in `__init__.py`.** The clean break is decided and not
   being relitigated. But the import name stays `dash_model_viewer` while the
   class name changes `DashModelViewer` → `ModelViewer`, so every existing user
   (~253 downloads/month) gets a bare `AttributeError` on upgrade. Six lines that
   raise a *descriptive* error naming the migration guide is not a compatibility
   promise — it is an error message. Recommend adding it.
3. **Demo model licensing — this is the urgent one.** `usage_tests/` and
   `assets/` currently contain `kara_-_detroit_become_human.glb` and
   `thor_and_the_midgard_serpent.glb` ✅, committed to a **public** GitHub repo
   today with no attribution. Kara is a Quantic Dream / Sony character. This is
   a live takedown risk that exists before any deploy, and republishing it on an
   indexed CDN makes it materially worse. Replace with Google's own model-viewer
   samples and Khronos glTF sample models. Treat as higher priority than the
   rebuild itself.
</content>
