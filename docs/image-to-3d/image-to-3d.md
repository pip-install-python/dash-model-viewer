---
name: Image to 3D
description: Upload a picture and get a real .glb — Claude reads the image and chooses the carving parameters, and deterministic code cuts the relief.
endpoint: /image-to-3d
package: dash_model_viewer
icon: mdi:image-filter-hdr-outline
lastmod: 2026-08-09
---

.. llms_copy::Image to 3D

.. toc::

### What this is, stated plainly

This is **not** photogrammetry and not neural reconstruction. One photograph
does not contain the back of an object, and nothing here pretends otherwise.

It carves a **relief** — a bas-relief slab, the way a coin or a carved panel is
3D. The image's brightness becomes height, the image itself becomes the surface
texture, and the result is a solid object you can orbit, light and place in AR.

For faces, logos, leaves, coins, lettering and hand-drawn shapes that is
genuinely the right answer. It works on any image, and the geometry costs
nothing to produce.

---

### Try it

.. exec::docs.image-to-3d.relief_page
    :code: false

.. source::docs/image-to-3d/relief_page.py

The page opens on a relief of this site's own logo, carved with **default
parameters and zero API calls** — so the geometry half is visibly working
before anything is spent.

---

### Where the model earns its place

The geometry is pure arithmetic. The *parameters* are a judgement call, and the
wrong ones produce a puddle or a cliff — so Claude looks at the image and
chooses them. Vision in, structured parameters out, code does everything after.

| Parameter | What it decides |
| :-- | :-- |
| `background` | whether a flat backdrop is cut away — **the one that matters most** |
| `depth_profile` | `linear` / `soft` / `punchy` / `stepped` — how brightness maps to height |
| `depth_scale` | relief depth as a fraction of width; a coin is ~0.04, a carved panel ~0.12 |
| `invert` | whether the subject's *dark* tones should stand proud (ink, engraving) |
| `metallic` / `roughness` | the material of the finished carving, not of the thing photographed |
| `alt` | one sentence for a screen-reader user — `alt` is a required prop |

On a stylised astronaut poster it returned:

> `soft` · `depth_scale 0.12` · `background cut_light` · matte
>
> *"Soft profile keeps the bright white suit from spiking while the flat light
> backdrop is cut away so the figure stands proud."*

On flat blue line-art it returned `punchy` with `invert: true` — because there
the dark strokes are the subject and everything else is paper.

That distinction is not something a fixed heuristic gets right, and it is not
something the user should have to know. It is exactly the shape of judgement a
vision model is good at.

---

### The bug that shaped the design

The first working version rendered every photograph as **a blank slab**.

Brightness becomes height. A subject photographed against white therefore makes
the *background* the tallest part of the carving, and sinks the subject into it.
The output is a flat plateau with a subject-shaped dent — and from the front it
looks like nothing happened at all.

Neither `invert` nor a different profile fixes it: inverting a photo raises the
shadows instead, which is a different wrong answer. The fix is a separate
decision — **is there a flat backdrop, and should it be cut away?**

```python
border = [edge pixels of the downsampled image]
reference = median(border)          # measured, not assumed
def is_backdrop(i):
    if mode == "cut_light":
        return lum[i] >= reference - tolerance and reference > 140
```

The reference tone is *sampled from the image's own border* rather than assumed
to be pure white, so "light" means whatever this particular image's edges
actually are — which survives JPEG noise, a soft vignette and an off-white
studio sweep.

The prompt then spends more words on this one parameter than on all the others
together, because it is the one that silently produces a plausible-looking
failure:

> Choosing `keep` on a white-background photo makes the BACKGROUND the tallest
> part of the carving and sinks the subject into it, so the whole thing reads as
> a blank slab. If the corners are all one flat colour, CUT.

---

### It degrades, it does not break

Every failure in the analysis step falls back to defaults and **still carves**:

| What went wrong | What happens |
| :-- | :-- |
| No `ANTHROPIC_API_KEY` | carved with defaults, noted in the status line |
| API error or timeout | carved with defaults, noted |
| Safety decline | carved with defaults, noted |
| Unparseable JSON | carved with defaults, noted |

The user always gets an object. That is deliberate: the model is choosing
*settings*, not doing the work, so its absence should cost quality rather than
the whole feature.

---

### Verifying geometry without a browser

A relief is 18 mm of depth on a 300 mm panel. Flat-shaded from the front it
looks exactly like a blank rectangle whether it worked or not, which makes
"looks fine" a useless check.

Two measurements settle it instead — and both are worth stealing for any
generated-geometry work:

```
z min/max        : -0.0046 → 0.01841        (back plate → peak relief)
distinct levels  : 185
vertices at z=0  : 3,875                    (the transparent background, flat)
```

...and rendering the height field itself as a greyscale image, where the
astronaut is immediately legible: suit proud, visor and gloves recessed,
background at exactly zero.

**Render the data, not the scene.** A picture of the parameter you care about
beats a picture of the object every time.

---

### Full 360° is a different pipeline

To get all sides you have to *generate* the ones the camera never saw. The
approach that works is the one in the SailsBoard object generator: the front
view goes in, five more orthographic views come out, each conditioned on the
front as an **identity lock** plus the already-approved views for consistency —
and those six views are exactly the six faces of a textured box.

Its hard-won lessons transfer intact:

- **"If any later reference disagrees with Reference 1, Reference 1 wins."**
  Explicit precedence, because consistency chains drift.
- **A measured COLOR LOCK split by role** — body colours versus outline ink.
  Naming raw hex values alone backfired: the outline shade was legitimately
  dominant, so told "build from these colours" the model rendered whole unseen
  faces in it.
- **Explicit relative proportions** — *"the front face is 3 tiles wide, but this
  side profile is 1 tile wide"* — because a model told only "draw the side"
  draws the front's proportions and then squashes them.
- **One rule per observed failure.** No scene, no isometric drift, no contact
  sheets. Each line kills something that actually happened.

That costs one image-generation call per view. This page deliberately does the
zero-generation half — and for the subjects it suits, the relief is not a
compromise but the correct object.

For geometry from a description rather than a picture, see
[Generative 3D art](/generative-3d).
