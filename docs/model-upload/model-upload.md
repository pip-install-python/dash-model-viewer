---
name: Model Upload
nav: Model Upload
description: Drop a .glb file onto the page and render it immediately, with a readout of what is actually inside the file.
endpoint: /model-upload
category: Viewing
order: 5
package: dash_model_viewer
icon: mdi:cube-scan
lastmod: 2026-09-13
---

.. llms_copy::Model Upload

.. toc::

## Open your own model

Every other page here hands `<model-viewer>` a model *this site* chose. This one
hands it yours. Choose a `.glb` and it renders — and the panel beside it says
what the file actually contains, which is usually the thing you wanted to know.

.. exec::docs.model-upload.model_upload

.. source::docs/model-upload/model_upload.py

---

## Why `.glb` and not `.gltf`

They are the same format with different packaging, and only one of them can
survive being uploaded on its own.

A `.gltf` file is JSON that **points at** its buffers and textures —
`scene.bin`, `colour.png`, a folder of images. Upload the `.gltf` by itself and
those neighbours stay on your machine, so the viewer gets a description of a
model whose geometry is missing. A `.glb` is the same data with the JSON and
every buffer packed into one binary container, which is exactly what makes it
uploadable.

That is also why the demo models across this site are `.glb`: one request, one
file, nothing to lose.

---

## The file is identified by its contents

A browser's idea of a file's type comes from its extension, and it is often
`application/octet-stream` — or nothing. So the type is not trusted here. The
first twelve bytes of a binary glTF are a fixed structure, and they cannot be
wrong about what the file is:

| Bytes | Meaning | Checked |
| :-- | :-- | :-- |
| 0–3 | the magic number `glTF` | it is that, or it is not a `.glb` |
| 4–7 | the format version | must be `2` |
| 8–11 | the total file length | must equal the bytes actually received |

The third check is the useful one: a file that says it is larger than it is was
truncated in transit, and the viewer would fail to draw it with no explanation.
Here it is named.

Refusals say which rule was broken and what was seen, because "invalid file"
tells you nothing about how to succeed next time. The rules themselves live in
`lib/uploads.py` alongside the image rules used by
[Texture Upload](/texture-upload) and [Sculpt from an Image](/sculpt-from-image)
— one place, so the three pages cannot drift into stating different caps.

| Rule | Value |
| :-- | :-- |
| Accepted | binary glTF (`.glb`), version 2 |
| Size cap | 32 MB |
| Written to disk | Never |
| Sent to a third party | Never |

The cap is larger than the 3 MB ceiling on the sculptures this site *generates*,
because a real exported or scanned asset is routinely tens of megabytes. It is
still a ceiling: the bytes make a round trip and come back as a `data:` URL in
the page.

---

## Reading the file rather than only drawing it

The panel is produced by `lib/glb.summarize()`, which parses the header and the
JSON chunk **only** — no buffers are decoded, so describing a 30 MB model costs
the same as describing a 30 KB one.

Triangle count is the number worth knowing. It is summed from the accessor
behind each primitive's indices, so it is the count the GPU will actually draw
rather than a figure from the exporter's dialog.

The **Animations** row pairs with [Animation](/animation): if a file reports
clips here, that page's controls will drive them. **Textures** answers the
question [Texture Upload](/texture-upload) raises — whether a model arrived
already carrying its own imagery, or whether what you are seeing is flat
material colour.

**Extensions** is worth a glance on somebody else's export. `<model-viewer>`
implements a subset of glTF's extensions; one that is listed here and not
supported is the usual reason a model renders but looks wrong — the variants
machinery behind [Model Switching](/model-switching) is
`KHR_materials_variants`, and it appears in this row when a file carries it.
