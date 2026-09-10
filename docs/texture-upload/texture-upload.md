---
name: Texture Upload
nav: Texture Upload
description: Upload a PNG or JPEG and have it replace the model's base-colour texture in the 3D scene, not as a flat overlay.
endpoint: /texture-upload
category: Viewing
order: 4
package: dash_model_viewer
icon: mdi:image-plus-outline
lastmod: 2026-09-10
---

.. llms_copy::Texture Upload

.. toc::

### Painting an upload onto the model

Upload an image and it becomes the model's surface — wrapped onto the
geometry, lit by the scene, and still there when you orbit. Not a poster and
not a 2D preview beside the viewer.

.. exec::docs.texture-upload.texture_upload
    :code: false

.. source::docs/texture-upload/texture_upload.py

---

### What happens to your upload

Worth stating plainly, because "upload" usually means "we keep it":

- The image travels with the callback request and is **never written to
  disk**. It is decoded once, in memory, only to measure its size.
- Nothing stores it. It lives in a `dcc.Store` in **your own browser** and is
  gone when you close the tab.
- It is not sent to any third party, and no AI model sees it. This page makes
  no network call of its own.

| Rule | Value |
| :-- | :-- |
| Accepted types | PNG, JPEG |
| Size cap | 4 MB decoded |
| Written to disk | Never |
| Retained after the tab closes | No |

SVG is rejected on purpose. It is a scriptable document rather than an image,
and this one is handed straight to the DOM.

---

### Why this one needs a clientside callback

Most of this site exists to show that `<model-viewer>` does **not** need
hand-written JavaScript any more — the camera, load state, dimensions, AR
status and hotspot clicks are all ordinary Dash props now.

Swapping a material's texture is the exception, and the reason is worth
knowing. `createTexture()` and `setTexture()` are **imperative calls on the
element**, and 1.0.0 deliberately ships no imperative surface — no `play()`,
no `pause()`, no programmatic `activateAR()`. There is no prop to set, so this
is one of the few places where the escape hatch is JavaScript rather than
`attributes` or `mv_*`.

The validation is not in that JavaScript. Type and size are checked in Python,
in a plain function with no Dash imports, so the rules are testable without a
browser:

```python
validate_texture(contents, filename) -> (data_url_or_None, message)
```

---

### The failure that would otherwise be silent

A material only accepts a base-colour texture if it already **has** one. Feed
this page a model whose materials carry no `baseColorTexture` slot and the
upload succeeds, the texture is created, and absolutely nothing changes on
screen.

So the clientside half counts what it touched and says so —
`Applied to 2 of 3 materials` — rather than returning quietly. An upload that
appears to do nothing is indistinguishable from a broken page, and this page
would have been the second kind of bug the component review spent its time
on: a feature that is wired, documented, and unobservable.
