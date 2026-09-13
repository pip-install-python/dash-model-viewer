---
name: Animation
nav: Animation
description: Play a model's built-in animation clips, switch between them with a crossfade, and pause — entirely through attributes, with the clip list reported by the model itself.
endpoint: /animation
category: Interaction
order: 3
package: dash_model_viewer
icon: mdi:run-fast
lastmod: 2026-09-12
---

.. llms_copy::Animation

.. toc::

### Clips come from the model, not from the page

A `.glb` can carry animation clips, and `model_info["animations"]` lists the
ones it has. Robot Expressive carries fourteen — `Dance`, `Death`, `Idle`,
`Jump`, `No`, `Punch`, `Running`, `Sitting`, `Standing`, `ThumbsUp`, `Walking`,
`WalkJump`, `Wave`, `Yes`.

The dropdown is filled from that prop, so this page would work unchanged if you
pointed `src` at a different animated model. A hardcoded list of those fourteen
names would have looked identical today and broken silently the first time
somebody swapped the model.

.. exec::docs.animation.animation
    :code: false

.. source::docs/animation/animation.py

It is the same prop that drives the variant dropdown on
[Model Switching](/model-switching) — one read-only payload, two features.

---

### Everything here is an attribute

There is no `animation_name` prop on `ModelViewer`, and that is deliberate:
1.0.0 ships **no imperative surface** — no `play()`, no `pause()`, no
`activateAR()`. So this entire page runs through the `attributes` escape hatch,
which makes it the most honest demonstration on the site of what that hatch is
for.

| Attribute | Effect |
| :-- | :-- |
| `autoplay` | Start playing on load. Without it the model loads in its bind pose, which reads as broken rather than as idle. |
| `animation-name` | Which clip. Changing it switches clip. |
| `animation-crossfade-duration` | Milliseconds to blend between clips. |
| `paused` | **Presence** pauses. |

```python
dmv.ModelViewer(
    id="viewer",
    src=ROBOT,
    alt="A robot, mid-wave",
    attributes={"autoplay": "", "animation-name": "Wave"},
)
```

.. admonition::`paused` is a boolean attribute, and that changes how you unset it
    :icon: radix-icons:exclamation-triangle
    :color: orange

    Resuming means **leaving the key out of the dict**, not setting it to
    `False` or `"false"`. An HTML boolean attribute is true by presence, so
    `paused="false"` is still paused.

    The shim removes any attribute that disappears between renders, so building
    a fresh dict each time — as the callback above does — is the pattern that
    works. `False` and `None` also remove, if you prefer to be explicit.

---

### Crossfade is the setting worth playing with

Set it to `0` and switching clips is a hard cut: the robot teleports from one
pose into the next. At `300` ms the poses blend and it reads as a character
changing its mind.

The default in `<model-viewer>` is `300`, and it is one of the few upstream
defaults this page leaves alone — it is already the right answer, which is
worth knowing before you reach for it.

---

### What is not here

Honest about the edges, because the gap is in the package rather than in this
page:

- **No scrubbing and no speed control.** `currentTime` and `timeScale` are
  JavaScript properties with no attribute equivalent, so they are unreachable
  from Python in 1.0.0. A clientside callback can drive them — see the one on
  [Texture Upload](/texture-upload) for the shape — but there is no prop.
- **No "animation finished" event.** `<model-viewer>` fires no such event, so
  there is nothing for the shim to forward.
- **No `appendAnimation`.** Composing clips from several files is an imperative
  API.

If you need any of those today, the escape hatch is JavaScript. If enough
people need them, they are props — which is the better answer and is not in
this release.

---

### Models that actually carry clips

Of the demo models this site uses, **only Robot Expressive has animations** —
measured by reading each `.glb`'s JSON chunk, not assumed. The astronaut, the
shoe, the sofa, the chair, the skull and the glass all have none, which is why
this page does not offer them: a dropdown that is empty for six of seven
choices is how [Model Switching](/model-switching) used to read before its
models were chosen for the feature it documents.
