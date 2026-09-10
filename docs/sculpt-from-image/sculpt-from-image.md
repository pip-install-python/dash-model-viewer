---
name: Sculpt from an Image
nav: Sculpt from Image
description: Upload a photograph and a vision model composes a sculpture that evokes it — a generated scene in the spirit of the picture, not a reconstruction of it.
endpoint: /sculpt-from-image
category: Generating
order: 4
package: dash_model_viewer
icon: mdi:image-filter-hdr
lastmod: 2026-09-10
---

.. llms_copy::Sculpt from an Image

.. toc::

### What this does, and what it does not

Upload a picture. A vision model looks at it and composes a sculpture out of
the same six primitives the rest of this site uses, and you watch it assemble.

**It is an interpretation, not a reconstruction.** Nothing here measures your
photograph. There is no depth estimation, no photogrammetry, no mesh fitting
and no point cloud. The model reads the image for its masses, proportions and
palette, and writes a parts list; `lib/glb.py` builds the triangles.

So a photo of your car returns something car-shaped, in your car's colours,
with your car's stance — and it is **not your car**. If that is not what you
want, nothing on this page will get you there, and it is better to know that
before you spend a call on it.

.. admonition::There is a second, deterministic image page
    :icon: radix-icons:info-circled
    :color: blue

    [Image to 3D](/image-to-3d) turns an image into geometry **without a model
    at all**: luminance becomes displacement and the result is a carved relief
    of your actual picture, pixel for pixel. It needs no API key, costs
    nothing, and is exact where this page is interpretive.

    Use that one when you want *your image, in relief*. Use this one when you
    want *a sculpture the image suggests*. They are different tools and the
    difference is not a matter of quality.

---

### Try it

.. exec::docs.sculpt-from-image.sculpt_from_image
    :code: false

.. source::docs/sculpt-from-image/sculpt_from_image.py

---

### What happens to your upload

| Rule | Value |
| :-- | :-- |
| Accepted types | PNG, JPEG |
| Size cap | 4 MB decoded |
| Written to disk | Never |
| Retained after the tab closes | No |
| Sent to a third party | **Yes — to the model provider, to be looked at** |

That last row is the one that differs from
[Texture Upload](/texture-upload), and it is the reason it is in the table
rather than in a footnote. Painting an image onto a model happens entirely in
your browser. Sculpting *from* an image cannot: the picture is sent to
Anthropic or OpenAI, because looking at it is the entire feature.

The rules themselves live in `lib/uploads.py` and are shared with the texture
page, so the two cannot drift into stating different caps.

---

### It is the same pipeline as the text sculptor

Everything downstream of the model is identical to
[Generative 3D](/generative-3d): the same JSON schema, the same clamps on size
and part count, the same sRGB-to-linear colour conversion, the same glTF
writer, the same `data:` URL delivery with no upload store.

The only difference is the input. Where that page sends a sentence, this one
sends a picture — and one extra paragraph of system prompt telling the model
to read masses, proportions and palette, and explicitly **not** to attempt
text, faces or fine surface detail. Those are what make an interpretation look
like a failed copy rather than a deliberate one.

Because the pipeline is shared, so is the spend gate: one call per sculpt,
metered against the same hourly ceiling as every other generating page on this
site. Streaming the assembly adds no model calls — the picture is read once.

---

### Watching it build

The build runs on a background thread and the viewer is re-pointed at a
complete `.glb` after each part, so the sculpture appears piece by piece. That
is the same `lib/build_stream.py` seam `/generative-3d` uses; see
[Generative 3D](/generative-3d#it-takes-about-35-seconds-and-it-has-to-say-so)
for why the progress store is a file rather than a dict, and why streaming per
part must never become charging per part.

---

### Choosing the model

The dropdown offers the Claude models, plus the GPT models when
`CHATGPT_API_KEY` is set on the host. The line under it always says which you
are getting and why — an absent model needs explaining, or it reads as a broken
page.

Two things decide what appears:

- **Discovery.** The GPT list is fetched from `GET /v1/models` on this host's
  own key at boot, not written into the source. A model id that has been
  retired would otherwise be an outage the first time somebody selected it.
- **Pricing.** A model is offered only if this build can also *price* it.
  `lib/spend.py` prices an unknown model at `$0.00`, so an unpriced model would
  pass the budget ceiling as though it were free rather than failing against
  it. Discovery decides what exists; pricing decides what is safe to meter.

The list is filled when the page is **viewed**, not when it is imported. Page
modules are imported while Dash registers pages — before `run.py` warms
discovery — so a layout that read the list at import froze the Claude-only set
permanently, whatever key was set. See `lib/model_picker.py`.

---

### What it costs, before and after

The estimate sits under the model picker and re-prices itself when you change
the model — choosing Opus over Haiku is choosing a 5x bill, and the only moment
that is useful is *before* the click. It also shows what is left of this shared
host's hourly ceiling.

That figure is an **upper bound, not a guess**: `lib/spend.py` prices every
call as though it used its whole output budget. The number reported after the
run is measured from the provider's own token counts and is nearly always
lower.

The result line then says what the run *actually* cost, to four decimal places
— two would render most sculpts as `$0.00`, which reads as free rather than as
cheap.
