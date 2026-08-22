---
name: Augmented Reality
description: Place a model in a real room — and the default that silently disabled WebXR on Android for the whole life of 0.0.1.
endpoint: /augmented-reality
package: dash_model_viewer
icon: mdi:augmented-reality
lastmod: 2026-08-08
---

.. llms_copy::Augmented Reality

.. toc::

### The bug this release exists to fix

`ar_modes` in 0.0.1 defaulted to:

```
"basic_annotations scene-viewer quick-look"
```

**`basic_annotations` is not an AR mode.** It is the name of a folder in the
repository's `usage_tests/` directory, copy-pasted into the default value.

The consequence was not a warning or an error. `<model-viewer>` reads the list,
does not recognise the first entry, ignores it, and falls through to the rest —
so AR still worked via Scene Viewer on Android and Quick Look on iOS. What was
missing was `webxr`, the mode that gives you in-page AR with your own UI and
the only one that supports custom AR prompts and placement.

So the package's flagship feature was degraded in every default installation,
for its entire published life, and nothing looked broken. The hub documentation
had always listed the *correct* value, so the docs and the code never agreed.

1.0.0 defaults to:

```
"webxr scene-viewer quick-look"
```

`tests/test_components.py` asserts both that `webxr` is present and that
`basic_annotations` is absent.

---

### AR in practice

.. exec::docs.augmented-reality.ar_viewer
    :code: false

.. source::docs/augmented-reality/ar_viewer.py

.. admonition::You cannot see this on a desktop
    :icon: radix-icons:mobile
    :color: yellow

    AR needs a phone. On a desktop browser the AR button does not appear at
    all, `ar_status` never fires, and everything above is inert — which is
    correct behaviour, not a broken example.

    Open **modelviewer.2plot.dev/augmented-reality** on an Android or iOS
    device to try it.

---

### The three AR modes

| Mode | Platform | What you get |
| :-- | :-- | :-- |
| `webxr` | Android, Chrome | In-page AR. Your own UI overlays the camera feed; `ar-prompt` and `ar-failure` slots work; placement and scale are reported back. |
| `scene-viewer` | Android | Hands off to Google's system AR viewer. Reliable, but it leaves your page. |
| `quick-look` | iOS, Safari | Hands off to Apple's AR Quick Look. Requires a USDZ — `<model-viewer>` generates one, or supply `ios-src`. |

Order matters: it is a preference list, and the first supported mode wins.
`"webxr scene-viewer quick-look"` means "in-page if you can, system viewer
otherwise".

---

### Reacting to the session

```python
@callback(Output("cart", "disabled"), Input("viewer", "ar_status"))
def in_ar(status):
    return status == "session-started"
```

`ar_status` values: `not-presenting`, `session-started`, `object-placed`,
`failed`. `ar_tracking` is `tracking` or `not-tracking`, and is how you know to
tell the user their room is too dark.

---

### iOS needs a USDZ

Quick Look does not read glTF. `<model-viewer>` converts on the fly, but the
conversion is lossy for complex materials and costs a round trip. For anything
you care about, supply your own:

```python
dmv.ModelViewer(
    id="viewer", src="/assets/chair.glb", alt="A chair",
    mv_ios_src="/assets/chair.usdz",
)
```

---

### `ar_scale`

`"auto"` (default) lets AR place the model at real-world scale, derived from
the glTF's units. `"fixed"` keeps the model's own scene units regardless.

Use `"auto"` for anything a user might want to check the size of — furniture,
appliances, equipment. Use `"fixed"` when the model is not a real object, or
when its units are not trustworthy.

.. admonition::Serve over HTTPS
    :icon: radix-icons:lock-closed
    :color: blue

    WebXR requires a secure context. On `http://` — including a plain
    `localhost` tunnel to a phone — the AR button will not appear, and there
    will be no error explaining why.
