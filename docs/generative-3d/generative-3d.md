---
name: Generative 3D Art
nav: Generative 3D
description: Describe a sculpture and get a real .glb — with Claude as a scene compiler, not a mesh generator, and every triangle built by deterministic Python.
endpoint: /generative-3d
category: Generating
order: 2
package: dash_model_viewer
icon: mdi:shape-plus-outline
lastmod: 2026-08-09
---

.. llms_copy::Generative 3D Art

.. toc::

### The bet

Ask a language model for a mesh and you get plausible nonsense — vertex lists it
cannot see, winding orders it cannot check, normals it cannot verify. There is
no feedback loop, so there is no way for it to be right except by accident.

Ask it *"what shape is a lighthouse"* and you get **a tall weathered cylinder, a
red cone on top, a small glowing sphere inside, a dark ring around the
gallery** — which is a thing code can build exactly.

So the model never emits geometry. It emits a **parts list**, and
`lib/glb.py` — a dependency-free glTF 2.0 writer — turns that into a real
`.glb`. The model supplies judgement; Python supplies triangles.

That split is why this is cheap, inspectable, reproducible, and needs no
third-party 3D service at all.

---

### Try it

.. exec::docs.generative-3d.sculptor
    :code: false

.. source::docs/generative-3d/sculptor.py

Orbit it. Put it in AR on a phone. It is a real glTF file, not a picture of one.

---

### The vocabulary

Six primitives, and nothing else:

| Shape | `size` means |
| :-- | :-- |
| `box` | width, height, depth |
| `sphere` | radius |
| `cylinder` | radius, height |
| `cone` | radius, height |
| `torus` | radius, tube thickness |
| `plane` | width, depth (a ground card) |

Each part carries a position, a rotation, and a PBR material — base colour,
metallic, roughness, emissive strength. That is the entire surface the model
writes to.

Constraining the vocabulary this hard is what makes the output reliable. There
is no syntax to get wrong, no topology to corrupt, and every field has a
meaningful clamp.

---

### The prompt does the artistic work

The schema decides what is *possible*; the system prompt decides whether the
result is *any good*. Three sections earn their place:

**Coordinates, stated as a physical fact.** `+Y` is up, the sculpture stands on
`y=0`, and `position` is the *centre* of a part — so a 1.4 m cylinder resting on
the ground has `position.y = 0.7`, not `0`. Without that last sentence, half the
parts sink through the floor, because "put it on the ground" and "centre it at
zero" are the same instruction to something that has never stood on a floor.

**Composition rules with a stated reason.**

> Between 5 and 28 parts. Fewer than 5 reads as a diagram; more than ~25 reads
> as noise at a glance. Vary scale deliberately: a few large masses that carry
> the silhouette, then smaller parts for detail. Rotation is free and underused
> — tilt, lean and offset parts rather than stacking everything axis-aligned.

**A palette rule, which is the single highest-return line:**

> Pick a deliberate palette of three or four colours and reuse them. A
> different colour per part looks like a test scene, not a sculpture.

Without it you reliably get twenty parts in twenty colours. It is the
difference between a sculpture and a bar chart.

.. admonition::Borrowed from a pipeline that had already learned this
    :icon: radix-icons:lightning-bolt
    :color: blue

    The palette rule is a direct descendant of the **COLOR LOCK** in the
    SailsBoard object generator, which measures the actual colours from a
    reference image and splits them by *role* — body colours versus outline
    ink. Naming raw hex values alone backfired there: the outline navy was a
    legitimately dominant colour, so told "build from these colours" the model
    rendered whole unseen faces in it.

    The lesson generalises past pixel art: **tell the model what each colour is
    FOR, not just which colours exist.**

---

### Shape is not sanity

Structured output guarantees `size.x` is a number. It does not guarantee the
number is sane. Everything is re-checked in `lib/sculptor.py`:

| Guard | Why |
| :-- | :-- |
| ≤ 28 parts | ~1.5 KB of geometry each; "a city" would exceed any data URL |
| every dimension ≤ 4 m | one runaway scale makes everything else invisible |
| within 5 m of origin | a part at `z = 900` silently breaks camera framing |
| roughness ≥ 0.05 | 0 is a perfect mirror and reads as a black hole |
| unknown `shape` dropped | with a note, not silently |
| ≤ 3 MB output | the practical data-URL ceiling |

Each clamp reports itself in the status line rather than being applied quietly.

#### The one that is not a clamp

```python
# glTF baseColorFactor is LINEAR, not sRGB.
return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
             for c in srgb)
```

The model returns `#A8A29A` because that is how humans write colour. glTF
expects linear values. Passing the sRGB numbers straight through renders every
palette visibly washed out — and it looks like a *lighting* problem, so it
sends you off tuning `exposure` for an hour.

---

### No upload store, on purpose

The finished `.glb` is handed to `ModelViewer` as a **`data:` URL**:

```python
src = "data:model/gltf-binary;base64," + base64.b64encode(glb).decode()
```

`<model-viewer>` accepts it — three.js's `FileLoader` carries an explicit
`/^data:.*,.*$/` branch, which you can find in the vendored bundle.

That is a design decision, not a shortcut. The obvious alternative is a server
route backed by a dict of generated files, and an in-memory store with no cap,
no TTL and no auth is a memory-growth vector the moment the site is public. The
data URL has no store to grow, nothing to expire, and nothing to clean up. The
cost is a size ceiling, which is exactly why the part budget is small.

---

### It takes about 35 seconds, and it has to say so

Measured on this page: **~36 s** for a sculpt, against ~8.5 s for the image
page's vision call and ~4 s for the [Scene Director](/scene-director). The
composition reasoning is genuinely the slow part — deciding twenty-five parts,
their placement and a coherent palette is not a lookup.

That length changes what the UI owes the user. The first version had no busy
state at all: you clicked *Sculpt*, nothing moved, and there was no way to tell
a slow call from a dead one. The fix is Dash's `running=`, which sets props for
the duration of the callback and restores them after:

```python
running=[
    (Output("g3-busy", "visible"), True, False),   # LoadingOverlay
    (Output("g3-go", "loading"), True, False),     # spinner in the button
    (Output("g3-prompt", "disabled"), True, False),
    (Output("g3-working", "display"), "block", "none"),
]
```

Two details that are easy to get wrong:

- **Nothing in `running` may also be an Output the callback returns.** Both
  would write the same prop and the order is not defined. A test asserts the
  two sets stay disjoint.
- **The overlay sits *over* the viewer rather than replacing it**, so the
  previous sculpture stays on screen while the next one composes. Swapping in a
  spinner throws away the thing the user is comparing against.

The estimate shown to the user is measured, not guessed. An estimate that is
too low is worse than none: at twenty seconds of "10 to 20 seconds" the user
concludes it has hung and clicks again.

### Cost

- **One call per sculpt**, `max_tokens=4000`, `effort="medium"` — the
  composition reasoning is real but short.
- At ~36 s a request holds a worker for a long time. `render.yaml` runs
  gunicorn with `--timeout 120` and `--threads 4`, so a sculpt cannot wedge the
  single free-tier worker; dropping either of those would make it possible.
- `stop_reason` is checked before `content` is read.
- No key configured means the button explains itself; it never returns a stub
  that looks like it worked.
- `tests/conftest.py` blanks `ANTHROPIC_API_KEY`, so no test run can spend
  money.

---

### Where it goes next

The parts list is a *scene graph*, so the obvious extensions are cheap:

- **Variations.** Re-run with the same manifest plus "make it taller / colder /
  more ruined" and diff the parts.
- **Animation.** glTF supports node animation; the writer does not emit it yet,
  but the node structure is already there.
- **Hand-editing.** The manifest is JSON. Nothing stops a user tweaking a
  colour and rebuilding — the model is not in that loop at all.

For turning an image into geometry rather than a description, see
[Image to 3D](/image-to-3d).
