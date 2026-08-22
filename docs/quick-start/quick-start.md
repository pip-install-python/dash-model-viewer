---
name: Quick Start
description: Install the package, put a 3D model on the page, and understand what got injected.
endpoint: /quick-start
package: dash_model_viewer
icon: mdi:cube-outline
---

.. llms_copy::Quick Start

.. toc::

### Install

```bash
pip install dash-model-viewer
```

One dependency: `dash>=4.1`. Google's `model-viewer` bundle is **inside the
wheel** — there is no npm step, no CDN request at runtime, and nothing to add
to `external_scripts`.

---

### Your first viewer

Two props are required — `src` and `alt` — and one is strongly advised:
`style`, because the element has no intrinsic size and will collapse to nothing
without a height.

.. exec::docs.quick-start.basic_viewer
    :code: false

.. source::docs/quick-start/basic_viewer.py

Drag to orbit. Scroll to zoom. On a phone, the AR button in the corner opens
the model in your room.

---

### What just happened

Importing `dash_model_viewer` registers a Dash **hook**, which injects two
scripts into every page:

| Script | Size | What it is |
| :-- | :-- | :-- |
| `vendor/model-viewer-umd.min.js` | ~1 MB | Google's `model-viewer` 4.3.1, vendored verbatim |
| `dash_model_viewer.js` | ~13 KB | The Dash ↔ custom-element shim |

Both are served by *your* server from the installed wheel, so the component
works offline, behind a corporate egress proxy, and under a strict
`script-src` Content-Security-Policy. The version is pinned by your lockfile
rather than by whatever a CDN is serving today.

.. admonition::That 1 MB is real
    :icon: radix-icons:exclamation-triangle
    :color: yellow

    The bundle loads on every page that imports the package, eagerly and
    synchronously. That is the price of having the custom element defined
    before Dash mounts — see [Why it loads that way](#why-it-loads-that-way).
    If your app has one 3D page out of thirty, import the package in that page
    module rather than in `app.py`.

---

### Serving the bundle from elsewhere

To use a CDN or an internal mirror instead of the vendored copy:

```python
import dash_model_viewer as dmv

dmv.configure(use_cdn=True)                         # public jsDelivr
dmv.configure(use_cdn="https://cdn.example/mv.js")  # your own mirror

app = Dash(__name__)
```

Call it at module scope. Dash reads the hook's resource list while generating
the index page, so a `configure()` buried in a callback or a lazily-imported
page module may or may not take effect depending on which request arrives
first — which is worse than never working at all.

---

### Why it loads that way

Not a detail, and worth knowing before you "optimise" it.

`<model-viewer>` is a custom element. If its definition has not executed by the
time Dash mounts your layout, the browser renders an unknown, unsized element
and you get a blank box — sometimes, depending on network timing. Version
0.0.1 fought this with `customElements.whenDefined()` and a runtime-injected
`<script type="module">`.

The fix is ordering, not defensive code. Dash's index ends:

```html
<footer>
    {%config%}
    {%scripts%}     <!-- every <script src>, hook scripts last -->
    {%renderer%}    <!-- inline: new DashRenderer(...) -->
</footer>
```

`{%renderer%}` is the inline statement that actually mounts the app. A
**classic** script in `{%scripts%}` runs before the parser reaches it, so the
element is always defined in time. A `type="module"` script is deferred until
after document parse — i.e. after `new DashRenderer(...)` has already run — and
the race comes straight back.

So the package vendors the **UMD** build, and never sets `type`, `async` or
`defer`. All three are asserted by the test suite, because none of them fail
loudly — they fail as "sometimes the model doesn't render, on someone else's
machine".

---

### Next

- [Events and callbacks](/events-and-callbacks) — the camera, load state and model
  dimensions as ordinary Dash props.
- [Slots and hotspots](/slots-and-hotspots) — labels anchored to the geometry.
- [Augmented reality](/augmented-reality) — including the default that was
  broken until 1.0.0.
