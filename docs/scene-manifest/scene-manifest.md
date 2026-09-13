---
name: Scene Manifest
nav: Scene Manifest
description: The versioned JSON a generated sculpture is made of — a complete, deterministic description you can export, edit by hand, and render again without paying a model.
endpoint: /scene-manifest
category: Reference
order: 5
package: dash_model_viewer
icon: mdi:code-json
lastmod: 2026-09-12
---

.. llms_copy::Scene Manifest

.. toc::

### The manifest *is* the sculpture

When [Generative 3D](/generative-3d) produces a model, the model does not
produce geometry. It produces this:

```json
{
  "version": 1,
  "name": "Lighthouse",
  "notes": "a tapered tower with a warm lamp",
  "parts": [
    {
      "color": "#E8E4DC",
      "emissive_strength": 0.0,
      "metallic": 0.0,
      "name": "tower",
      "position": {
        "x": 0,
        "y": 1.0,
        "z": 0
      },
      "rotation": {
        "x": 0,
        "y": 0,
        "z": 0
      },
      "roughness": 0.8,
      "shape": "cylinder",
      "size": {
        "x": 0.4,
        "y": 2.0,
        "z": 0.4
      }
    },
    {
      "color": "#FFC15E",
      "emissive_strength": 1.0,
      "metallic": 0.1,
      "name": "lamp",
      "position": {
        "x": 0,
        "y": 2.1,
        "z": 0
      },
      "rotation": {
        "x": 0,
        "y": 0,
        "z": 0
      },
      "roughness": 0.3,
      "shape": "sphere",
      "size": {
        "x": 0.18,
        "y": 0.18,
        "z": 0.18
      }
    }
  ],
  "provenance": {
    "generated": "2026-09-12",
    "model": "hand-authored",
    "prompt": "a brutalist lighthouse at dusk",
    "usd": 0.0
  }
}
```

### Try the round trip

Pick a sample, edit it, render it. Nothing here calls a model — the manifests
are committed JSON, so this works on a host with no API key.

.. exec::docs.scene-manifest.round_trip
    :code: false

.. source::docs/scene-manifest/round_trip.py

*Load the invalid fixture* shows the importer's **own** refusal message against
a committed broken file, rather than an error message typed into this page.

---

`lib/glb.py` turns that into a real glTF. Every triangle is deterministic
Python: the same manifest produces **byte-identical** `.glb` output. That is
what makes the round trip below an identity rather than an approximation.

A generated sculpture is therefore not a one-off image you either keep or lose.
It is a short, readable document you can save, edit in a text editor, hand to
someone else, and render again for free.

---

### A manifest is sufficient on its own

**The renderer never needs the prompt.** Everything required to reproduce the
`.glb` is in `parts`; nothing in the manifest refers to a model, a key, or the
sentence that produced it.

That matters for the obvious reason — you can render one on a host with no API
key, which is what this site does — and for a less obvious one: it means the
format has no dependency on a provider's output staying stable.

Where the sentence *is* worth keeping, it goes in an optional `provenance`
object that the renderer reads **not at all**:

```json
"provenance": {
  "prompt": "a brutalist lighthouse at dusk",
  "model": "claude-opus-5",
  "usd": 0.0871,
  "generated": "2026-09-12"
}
```

Delete it and the sculpture is unchanged. Keep it and you know what a file cost
and where it came from.

---

### Units and frame, stated once

| | |
| :-- | :-- |
| Length | **metres** |
| Angles | **degrees**, not radians |
| Handedness | right-handed |
| Up | **+Y** |
| Away from the viewer | −Z |
| Ground | the sculpture stands on `y = 0` |
| Scene bound | nothing further than **5 m** from the origin; no single dimension over **4 m** |

`position` is the **centre** of a part. A 1.4 m cylinder standing on the ground
has `position.y = 0.7`, not `0` — which is the single most common thing to get
wrong by hand, because "put it on the ground" and "centre it at zero" sound like
the same instruction.

---

### Top level

| Field | Type | Required | Notes |
| :-- | :-- | :-- | :-- |
| `version` | integer | **yes, first key** | `1`. See **Versioning**. |
| `parts` | array | **yes** | The sculpture. `[]` is valid and renders nothing. |
| `name` | string | no | The viewer's `alt` text, and what the download filename is **derived from** — slugged, length-capped and given a fixed extension, never used raw. `"../../etc/passwd"` becomes `etc-passwd.glb`. |
| `notes` | string | no | One sentence about the idea. Nothing reads it. |
| `provenance` | object | no | Never read by the renderer. See above. |

**Unknown keys are rejected.** That is deliberate and it is the point of the
version number: if version 1 quietly ignored a key it did not know, a version 2
manifest using part groups would be *accepted* by a version 1 reader and render
without them — a sculpture missing pieces, with nothing said. Strictness is what
lets the version mean something.

---

### A part

Every field is required. Ranges are enforced, not advisory.

| Field | Type | Range | Notes |
| :-- | :-- | :-- | :-- |
| `name` | string | any | For your benefit. Not rendered. |
| `shape` | string | `box`, `sphere`, `cylinder`, `cone`, `torus`, `plane` | Anything else is refused by name. |
| `size` | `{x, y, z}` numbers | each `0.01`–`4` | Which components matter depends on the shape — see the table below. |
| `position` | `{x, y, z}` numbers | within 5 m of origin | The **centre** of the part. |
| `rotation` | `{x, y, z}` numbers | `-360`–`360` | Degrees. Applied X, then Y, then Z — see **Rotation order**. |
| `color` | string | `#RRGGBB` | Converted sRGB → linear into the glTF. |
| `metallic` | number | `0`–`1` | |
| `roughness` | number | `0.05`–`1` | `0` is a perfect mirror and reads as a black hole, so it is floored. |
| `emissive_strength` | number | `0`–`1` | Above `0` the part glows. `1` is the ceiling, not a soft one. |

And the whole scene: **at most 28 parts**, output **at most 3 MB**.

#### What `size` means, per shape

Only some components are read. The rest are ignored, which is worth knowing
before you spend time tuning one that does nothing.

| `shape` | `size.x` | `size.y` | `size.z` |
| :-- | :-- | :-- | :-- |
| `box` | width | height | depth |
| `sphere` | **diameter** | ignored | ignored |
| `cylinder` | **diameter** | height | ignored |
| `cone` | base **diameter** | height | ignored |
| `torus` | outer **diameter** | ignored | tube **diameter** |
| `plane` | width | ignored | depth |

**Diameter, not radius.** `lib/sculptor.py` passes `size.x / 2` to the
builders, so a sphere with `size.x = 0.4` is 0.4 m across. Reading it as a
radius gives you a model twice the size you meant, which is the kind of error
that looks like a units bug.

---

### Rotation order

Degrees, applied **X first, then Y, then Z, about the fixed world axes** —
extrinsic XYZ, equivalently intrinsic Z-Y-X. The composed rotation is
`Rz · Ry · Rx`.

This is stated because it is not guessable and it is not reproducible without
it: the same three numbers in a different order give a different object. It was
measured from `lib/glb.py`'s `_euler_to_quat`, not assumed, and a test pins the
resulting quaternion so the order cannot change silently.

```
rotation {"x": 90, "y": 0, "z": 0}  ->  quaternion (0.7071, 0, 0, 0.7071)
rotation {"x": 0, "y": 90, "z": 0}  ->  quaternion (0, 0.7071, 0, 0.7071)
```

---

### What a refusal looks like

A manifest is validated before anything is built, and a refusal **names the
field**. "Invalid manifest" tells you nothing you can act on.

| What is wrong | What you are told |
| :-- | :-- |
| `"version": 2` | the version, and that this build reads 1 |
| `"shape": "dodecahedron"` | the part index and the unrecognised shape |
| `"size": {"x": 40, …}` | the field, the value, and the 4 m bound |
| 29 parts | the count and the limit |
| `"metallic": "shiny"` | the field and that a number was expected |
| an unknown key | the key **and its path** — `parts[3].colour`, `provenance.cost` |
| `"emissive_strength": 3.0` | the field, the value and the `0`–`1` range |

---

### Versioning

- **`"version": 1`**, an integer, the first key on export.
- **A version this build does not know is refused**, with the number in the
  message, and is *not* partially read.
- **Version 1 will not change meaning.** The planned additions — part groups
  with a transform, so a wheel is defined once and instanced, and profile-based
  shapes (extrude, lathe) for arbitrary silhouettes — are additive and will
  arrive as **version 2**, with version 1 still readable.

That is the promise the number exists to make: a manifest exported today renders
the same way after those land.

---

### Export is byte-stable

Export writes sorted keys, fixed float precision and a trailing newline, so:

```
export(import(m)) == m          for every manifest this build accepts
import(export(scene))           renders byte-identical .glb output
```

Both are tests, not intentions. Byte-stability is also what makes two manifests
diffable — an unstable writer would show a diff on every export and hide the
one change you made.

---

### Importing obeys the upload rules

A pasted manifest is untrusted input from a visitor, so it takes the same path
as an image on [Texture Upload](/texture-upload), through the shared rulebook in
`lib/uploads.py`:

- **Size-capped**, with the cap stated on the page.
- **Validated against this schema** before anything is built.
- **Never written to disk.** No manifest store, no temp directory, no cleanup
  job — the same reasoning that keeps generated `.glb` output in a `data:` URL
  rather than a server-side store, and a test asserts neither exists.

A manifest cannot execute anything; it is primitives and numbers. Validation is
protecting you from a file that renders nothing and does not say why.

---

### Where these samples came from

Three samples and one deliberately broken fixture, all committed as JSON in
`docs/scene-manifest/samples/`:

| File | Why it exists |
| :-- | :-- |
| `lighthouse.json` | The example at the top of this page, byte for byte. Two parts. |
| `colonnade.json` | **Exactly 28 parts** — the inclusive limit, proven here rather than only in a test. |
| `brazier.json` | `emissive_strength` at its ceiling of `1.0`. |
| `INVALID-fixture.json` | Refused on purpose. Named so nobody mistakes it for a sample. |

**They are hand-authored, not model output**, and that is a deliberate change
from the original plan. Two reasons: a model will not produce *exactly* 28 parts
on request, and the limit is the thing worth proving; and a hand-authored file
costs nothing to regenerate when the schema gains a version 2. Their
`provenance.model` says `hand-authored` rather than naming a model that did not
write them.

This site carries no provider keys — it is documentation and does no production
spend ([why](/generative-3d)) — so nothing on this page calls a model.

That is the useful half of the format rather than a limitation to apologise for:
**the round trip works with no key at all.** Import a manifest, render it,
download the `.glb`. The model was only ever the manifest's author, and it has
already done its part.
