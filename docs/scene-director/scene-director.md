---
name: Scene Director
description: Describe a shot in plain language and let Claude stage it — grounded in the model's measured geometry, then clamped before anything reaches the browser.
endpoint: /scene-director
category: Generating
order: 3
package: dash_model_viewer
icon: mdi:movie-open-outline
lastmod: 2026-08-08
---

.. llms_copy::Scene Director

.. toc::

### Why this demo and not text-to-3D

The obvious AI demo for a 3D component is *type a prompt, get a model*. It is
the wrong one to build first, for a reason that has nothing to do with taste:
**it would work just as well on the broken 0.0.1.** It only needs `src`.

This one cannot. It needs the component to report what it is looking at, and to
accept a whole scene back as props — and 0.0.1 had no output props at all.

That makes it the end-to-end regression test for the entire rebuild wearing a
user interface. If the Scene Director works, the event plumbing works.

---

### Try it

.. exec::docs.scene-director.scene_director
    :code: false

.. source::docs/scene-director/scene_director.py

.. admonition::No key, no magic
    :icon: radix-icons:info-circled
    :color: blue

    If this host has no `ANTHROPIC_API_KEY`, the button returns a plain "the
    director is off" message rather than a stub that looks like it worked. The
    interesting parts — the grounding, the schema and the clamping — are in
    `lib/scene_director.py` and need no key to read.

---

### The loop

```
model_info + camera  ──►  grounded prompt  ──►  Claude (structured output)
                                                      │
                      props  ◄──  clamp + sanitise  ◄──┘
```

Two of those four steps do the real work, and neither is the API call.

#### 1. Grounding — the step that decides whether it works

The prompt carries the model's **measured** bounding box, in metres, straight
from `model_info`:

```
THIS MODEL, measured (metres):
  width(x)=0.294  height(y)=0.148  depth(z)=0.104
  available material variants: ['midnight', 'beach', 'street']

CURRENT CAMERA:
  orbit=15deg 78deg 0.42m  target=0m 0.07m 0m  fov=45deg

RULES — these are geometry, not style:
- Keep phi between 10deg and 170deg…
- Keep radius between 0.24m and 0.88m. Below that the camera is inside the mesh.
```

Without those numbers the model returns `"2.5m"` — a completely reasonable
radius for a *chair*, and about six metres outside a shoe. It is confidently
wrong, because nothing in the request says how big the object is.

This is the general lesson, not a model-viewer one: **an LLM writing
parameters for a physical system needs that system's measurements in the
prompt.** The component is what supplies them.

#### 2. Structured output

The schema is passed with the request, so the response is JSON of the right
shape or the call fails — no parsing, no retry loop, no "please respond with
only JSON" incantation:

```python
response = client.messages.create(
    model="claude-opus-5",
    max_tokens=1500,
    system=_system_prompt(model_info, camera),
    output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
    messages=[{"role": "user", "content": request}],
)
```

`effort="low"` because the reasoning here is short, and a docs-site demo should
not cost more than it needs to.

.. admonition::Structured outputs cannot express a free-form map
    :icon: radix-icons:exclamation-triangle
    :color: yellow

    The obvious schema for `attributes` is an object with
    `additionalProperties: {"type": "string"}`. The API rejects it outright:

    ```
    400 invalid_request_error — output_config.format.schema: For 'object' type,
    'additionalProperties: object' is not supported. Please set
    'additionalProperties' to false
    ```

    Every object in a structured-output schema must be closed. An **open key
    space therefore has to be modelled as a list of `{name, value}` pairs** and
    folded back into a dict afterwards. Enumerating the allowed attribute names
    instead would have thrown away the whole point of the parity hatch.

#### 3. Clamping — shape is not sanity

Structured output guarantees `camera_orbit` is a *string*. It does not
guarantee the string puts the camera outside the mesh. Every number is
re-checked against the geometry, and every adjustment is reported in the UI
rather than applied silently:

```python
if not 10 <= phi <= 170:
    phi = min(170.0, max(10.0, phi))
    notes.append(f"phi clamped to {phi:g}deg (pole roll)")
if not lo <= radius <= hi:
    radius = min(hi, max(lo, radius))
    notes.append(f"radius clamped to {radius:.2f}m for this model")
```

Unparseable values are discarded, not guessed at. A `variant_name` the file
does not contain falls back to the default.

#### 4. Sanitising — model output becomes DOM attributes

This one is a security boundary, and it is the part most worth copying.

The `attributes` dict is deliberately open — that is what makes the output
space the *entire* `<model-viewer>` attribute surface, including attributes
added upstream after this release. But open means the model could return
`src`, and `src` decides what the browser downloads.

```python
BLOCKED_ATTRIBUTES = frozenset(
    {"src", "ios-src", "poster", "environment-image", "skybox-image"}
)
```

**Never let model output set an attribute that fetches.** Everything on that
list points a user's browser at a URL. The rest of the surface — `exposure`,
`auto-rotate`, `orientation`, `shadow-softness` — changes only how the thing
already loaded is drawn, and is safe to hand over.

---

### What it actually returns

Two real responses for the shoe above, whose measured box is
0.294 x 0.148 x 0.104 m — so the clamp window for the radius is 0.24 m to
0.88 m:

> **"dramatic low three-quarter angle, focus on the sole"**
>
> ```json
> {
>   "camera_orbit": "40deg 118deg 0.36m",
>   "camera_target": "0m 0.05m 0m",
>   "field_of_view": "34deg",
>   "tone_mapping": "aces",
>   "shadow_intensity": 1.0,
>   "variant_name": null,
>   "attributes": {"exposure": "0.95", "shadow-softness": "0.4"}
> }
> ```
>
> *"I dropped the camera below the horizon at a 40° three-quarter turn so the
> sole tilts into view, with a tighter FOV and punchy ACES contrast for drama."*

`phi=118deg` is genuinely below the horizon, and `0.36m` sits inside the window
without needing a clamp — because the window was in the prompt.

> **"top-down, tight, soft shadow, midnight colourway"**
>
> ```json
> {
>   "camera_orbit": "0deg 15deg 0.32m",
>   "field_of_view": "28deg",
>   "shadow_intensity": 0.6,
>   "variant_name": "midnight",
>   "attributes": {"shadow-softness": "1", "exposure": "1.05"}
> }
> ```

That second one is the whole argument in one field. **`variant_name: "midnight"`
was only selectable because `model_info["variants"]` told the prompt the file
contained it.** Nothing on the server knows anything about that shoe. Point the
page at a different `.glb` and the available variants change with it.

---

### What makes the parity hatch interesting here

`attributes` is not a convenience for this page; it is what makes the feature
open-ended. The model can reach for `rotation-per-second`, `auto-rotate-delay`
or `orientation` without any of them being named props, and a `<model-viewer>`
5.x attribute nobody has written yet will work the same way.

The alternative — an enum of blessed props — would need extending every time
either upstream or the prompt got more ambitious. See
[Attributes and parity](/attributes-and-parity).

---

### Cost and posture

- **One call per click.** `max_tokens=1500`, `effort="low"`.
- **`stop_reason` is checked before `content` is read.** A safety decline
  returns HTTP 200 with an empty content list; indexing `content[0]` would
  raise instead of explaining.
- **The key is read at call time**, never cached at import, so rotating it does
  not need a redeploy.
- **The test suite blanks `ANTHROPIC_API_KEY`** in `conftest.py`, so no test
  run can ever spend money — `lib/backend.py` calls `load_dotenv()`, and a
  developer with a real key in `.env` would otherwise be billed by their own
  test suite.
- On a public host this page belongs behind an authenticated tier so spend is
  bounded by sign-ups rather than by traffic.

---

### Where this goes next

The same loop, pointed at a different output shape, is a **tour composer**:
ordered stops, each with a camera pose, a `Slot` hotspot anchored to real
geometry, and a caption. That produces a shareable artifact rather than a
single view, and it is what product configurators, museum pieces and technical
documentation all hand-write today.

The grounding, the clamping and the block-list are unchanged. Only the schema
grows.
