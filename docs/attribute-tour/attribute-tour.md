---
name: Attribute Tour
nav: Attribute Tour
description: The model-viewer attributes with no named prop — loading, reveal, scale, skybox, pan and tap locks, and the AR-only ones — each shown or honestly marked as unshowable.
endpoint: /attribute-tour
category: Reference
order: 4
package: dash_model_viewer
icon: mdi:tune-variant
lastmod: 2026-09-12
---

.. llms_copy::Attribute Tour

.. toc::

### Why this page exists

[Attributes and parity](/attributes-and-parity) argues that the `attributes`
dict and `mv_*` wildcards reach every attribute `<model-viewer>` has. This page
is the evidence: it drives eleven attributes that have **no named prop on
`ModelViewer`**, and says plainly which of them you cannot see from a desktop
browser.

It was written from an audit against `modelviewer.dev`'s own example pages.
Those eleven were reachable from this package on the day it shipped and
demonstrated nowhere — which is a documentation gap rather than a capability
one, and the kind the 1.0.0 review kept finding.

.. exec::docs.attribute-tour.attribute_tour
    :code: false

.. source::docs/attribute-tour/attribute_tour.py

The block under the viewer is the attribute dict as it reaches the element, so
you can read what each control actually sent.

---

### The viewer remounts on every change, deliberately

Every other page here changes a prop and lets the element update in place.
This one rebuilds the viewer.

`loading` and `reveal` only do anything **while a model is loading**. Toggling
them on a viewer that has already loaded does nothing whatsoever — so a page
that updated in place would look broken for precisely the two settings a reader
is least likely to believe. Remounting makes them observable.

The id is unchanged across the rebuild, so callbacks keyed on it keep working.
Only the element is new.

---

### What you can see from a laptop

| Attribute | Values | What to look for |
| :-- | :-- | :-- |
| `scale` | `"1 1 1"`, `"2 2 2"` | The model gets bigger. Note the shadow scales with it. |
| `disable-pan` | present | Two-finger drag (or right-drag) no longer slides the model sideways. |
| `disable-tap` | present | A single tap no longer recentres the camera on the tapped point. |
| `interaction-prompt` | `none` | The animated hand stops appearing after a few idle seconds. |
| `skybox-image` | an `.hdr` URL | The grey background becomes the environment, and the model is lit by it. |
| `skybox-height` | e.g. `2m` | Only with a skybox: lifts the horizon so the model sits *in* the scene rather than floating in a sphere. Alone it does nothing, which is why the control is nested under the skybox toggle. |
| `loading` | `auto`, `lazy`, `eager` | `lazy` defers until the viewer is near the viewport; `eager` fetches immediately. Watch the network panel, not the picture. |
| `reveal` | `auto`, `interaction` | `interaction` holds the poster until you click. |

`reveal="manual"` is deliberately absent from the control. It holds the model
until `dismissPoster()` is called — an **imperative method**, and 1.0.0 ships
no imperative surface, so there is no way to dismiss it from Python. Offering
the value would produce a viewer that never reveals, which is a trap rather
than a demonstration.

---

### What you cannot see from a laptop

These three are real, reachable and **not demonstrable here**. Listing them
with their values beats pretending the page covers them:

| Attribute | Values | Needs |
| :-- | :-- | :-- |
| `ar-placement` | `floor`, `wall` | A phone in AR. `wall` anchors the model to a vertical surface — the right choice for a picture frame or a television. |
| `xr-environment` | present | A WebXR session on Android. Lights the model with the room's estimated lighting instead of the `environment-image`. |
| `ios-src` | a `.usdz` URL | iOS Safari. Quick Look cannot read `.glb`, so an iOS AR path needs a second file. There is no named prop; use `mv_ios_src` or `attributes`. |

```python
dmv.ModelViewer(
    id="viewer", src="/assets/chair.glb", alt="A chair",
    mv_ios_src="/assets/chair.usdz",
    attributes={"ar-placement": "floor", "xr-environment": ""},
)
```

Walk those on [Augmented reality](/augmented-reality) with a real device. A
desktop browser will report AR as unavailable and tell you nothing about
whether the attributes landed.

---

### Boolean attributes, once more

`disable-pan`, `disable-tap` and `xr-environment` are true **by presence**. So:

```python
attributes={"disable-pan": ""}     # panning is off
attributes={}                      # panning is on
attributes={"disable-pan": "false"}  # STILL OFF — "false" is a present value
```

The shim removes any attribute that disappears between renders, so building a
fresh dict each time — as the callback on this page does — is the pattern that
works. `False` and `None` also remove, if you would rather be explicit than
rely on absence.

The same trap as `paused` on [Animation](/animation), and it is worth meeting
twice: it is the single most common way an `attributes` dict does the opposite
of what it reads like.
