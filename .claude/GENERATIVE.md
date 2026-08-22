# The generative layer — proposal

Written against the Claude API reference as of 2026-08-08. Model IDs and the
structured-output call shape below are current, not recalled.

---

## The argument, before the features

There is an obvious generative demo for a 3D component — *type a prompt, get a
model* — and I think it is the wrong one to build first. It showcases a
third-party text-to-3D vendor, costs real money per generation, and carries
licensing and moderation exposure on a public indexed site. Worse, it would work
just as well on the broken 0.0.1: it only needs `src`.

The demo worth building is the one that **cannot work on 0.0.1**.

`dash-model-viewer` 1.0.0 turns the component into a closed loop:

```
        model_info ─── dimensions, variants, animations ──┐
        camera ─────── current orbit / target / fov ──────┤
        scene_point ── click → real 3D position + normal ──┤
                                                          ▼
                                              prompt to Claude
                                                          │
                              structured JSON of viewer props
                                                          │
        camera_orbit, field_of_view, exposure, tone_mapping,
        variant_name, attributes{...}, Slot hotspots ◀─────┘
```

The component supplies the **grounding** (what this model actually is, in
metres) and consumes the **generation** (props). Neither direction exists in
0.0.1 — there are no output props at all, and hotspots are a list-of-dicts with
no way to hold arbitrary children. **The generative page is therefore the
end-to-end regression test for the entire rebuild.** If the AI demo works, the
event plumbing works. That is a much better argument for the version bump than
any prose in the CHANGELOG.

There is a second, sharper synergy. Because `ModelViewer` takes an `attributes`
dict (ARCHITECTURE §6b), **the model's output space is the whole model-viewer
attribute surface — including attributes this package has never heard of.** The
LLM can emit `environment-image`, `orientation`, `auto-rotate-delay`,
`disable-tap`, or anything Google ships in model-viewer 5.x, and it just works
with no release. That is a genuinely striking thing to demonstrate on a docs
page, and it is a *direct* consequence of an API decision — not a bolt-on.

---

## Tier 1 — Scene Director (build this)

**Page:** `/scene-director`. **Cost:** one short call per prompt.

A prompt box under the viewer. The user types intent, not parameters:

> *"dramatic low three-quarter angle, focus on the sole, dark studio lighting"*

The server builds a prompt containing the model's **measured** facts — pulled
from `model_info`, not guessed — and asks for a strict JSON scene.

### The grounding step is the whole trick

Without it the model invents a `camera_orbit` radius in the wrong units and the
camera ends up inside the mesh or a kilometre away. With it, the numbers land.

```python
from pydantic import BaseModel, Field
from anthropic import Anthropic

class Scene(BaseModel):
    camera_orbit: str = Field(description="theta phi radius, e.g. '45deg 70deg 2.5m'")
    camera_target: str = Field(description="X Y Z in metres, e.g. '0m 0.4m 0m'")
    field_of_view: str
    tone_mapping: str  # neutral | aces | agx | commerce
    shadow_intensity: float
    variant_name: str | None
    attributes: dict[str, str] = Field(
        description="Any other model-viewer attribute, kebab-case. "
                    "e.g. environment-image, exposure, orientation."
    )
    rationale: str = Field(description="One sentence, shown to the user.")

client = Anthropic()

resp = client.messages.parse(
    model="claude-opus-5",
    max_tokens=2000,
    system=(
        "You are a 3D staging director for Google's <model-viewer>. "
        "Return a camera and lighting setup that realises the user's intent.\n"
        f"Model bounding box (metres): {info['dimensions']}\n"
        f"Available GLTF variants: {info['variants'] or 'none'}\n"
        f"Current camera: {camera['orbit']} / target {camera['target']}\n"
        "Radius must stay within 0.8x-3x the bounding sphere. "
        "phi must be 0deg-180deg."
    ),
    messages=[{"role": "user", "content": user_prompt}],
    output_format=Scene,
)
scene = resp.parsed_output          # a validated Scene
```

### Then clamp it — never trust the numbers

Structured output guarantees the *shape*, not the *sanity*. This is the part
that separates a demo from a product, and it is worth showing in the docs
because every reader building an LLM→UI pipeline needs it:

```python
scene = clamp_to_bounding_sphere(scene, info["dimensions"])   # radius
scene = clamp_phi(scene)                                      # 0-180deg
scene = drop_unknown_variants(scene, info["variants"])
```

Then it is just a Dash callback returning props. `interpolation_decay` makes
the camera *fly* to the new pose rather than snap — the generation is visibly
an animation, which is what makes the page feel alive.

### Refinement is where the loop closes

"a bit lower, and warmer" as a follow-up sends the **current** `camera` output
prop back as context. The model is now editing a real state it can see, not
re-guessing from scratch. That is impossible in 0.0.1.

---

## Tier 2 — Tour Composer (build second)

**Page:** `/tour-composer`. **Cost:** one call per tour.

> *"Make a 5-stop guided tour of this engine for a first-year apprentice."*

Returns an ordered list of stops, each with a camera pose, a `Slot` hotspot
anchored to a real 3D position, and a caption. Rendered as a tour with
prev/next; `hotspot_click` jumps to a stop.

This is the one that reads as a **product** rather than a toy — it produces a
shareable artifact (a JSON tour definition the user can copy into their own
app), and it exercises `Slot`, the camera props, and `hotspot_click` together.
It is also the honest answer to "what would I actually use this for": product
configurators, museum pieces, technical documentation, and e-commerce all want
exactly this and currently hand-write it.

Grounding note: hotspot positions must come from `scene_point` (real geometry
via `positionAndNormalFromPoint`) or from bounding-box-relative anchors — never
from the model's imagination, or labels float in empty air.

---

## Tier 3 — Text-to-3D bridge (`examples/`, not deployed)

Prompt → a third-party generation API (Meshy, Tripo, Luma, Rodin) → `.glb` →
viewer. Flashy, and the thing people expect.

**Recommendation: ship it as `examples/text_to_3d.py` with a README, and do not
deploy it on the docs site.** Three reasons, all of which apply to a public
indexed host and not to a localhost demo:

1. Every generation costs real money to a vendor, with an anonymous write
   surface — the exact uncapped-spend vector REVIVAL §4 warns about.
2. Generated meshes are user content on a public site: moderation and IP
   exposure with no review step.
3. It showcases the vendor, not the component. The viewer is a passive `<img>`
   tag in that story.

If it is ever deployed, it belongs behind the `auth` tier with a hard per-user
cap, like every other keyed page.

---

## A small one worth doing anyway

**Alt-text generation.** `alt` is a *required* prop on `ModelViewer` and it is
an accessibility obligation, not decoration. A one-line "suggest alt text"
affordance — render a frame, describe it — is cheap, tasteful, and makes an
accessibility point the docs should be making regardless. Put it on the
quick-start page, not its own page.

---

## Cost and safety posture

Non-negotiable, and shaped by how these have bitten this network before:

- **Every AI page ships behind the `auth` tier** (REVIVAL §4). Spend is bounded
  by sign-ups and throttleable from the control board.
- **Blank the keys in dev and CI at the harness level**, not by remembering —
  the same `.claude/settings.json` pattern used in the petri-dish project. A
  `load_dotenv()` that quietly picks up a live key during a test run is the
  failure mode to design against.
- **Zero-secrets pytest must stay green** (STANDARD §8.1). With no key set, the
  generative pages must fail *closed* — 401/503, never a 200 with a stub that
  looks like it worked.
- **Per-request cap**: `max_tokens=2000` is ample for a scene; a tour needs
  ~4000. Neither needs streaming.
- **Model choice**: `claude-opus-5`. It is the default for good reason here —
  the task is spatial reasoning about a bounding box, which is exactly where a
  weaker model produces plausible JSON containing a camera inside the mesh.
  Adaptive thinking is on by default on Opus 5; `output_config={"effort":
  "low"}` is the lever if these calls turn out to be over-deliberated.
- **Never expose a raw prompt path to a third-party generation API** without a
  cap. That is Tier 3's whole problem.

---

## What I would build in what order

1. `events-and-callbacks` docs page — proves the output props (no AI).
2. **Scene Director** — the regression test with a UI.
3. **Tour Composer** — the one that looks like a product.
4. Alt-text affordance on quick-start.
5. Text-to-3D in `examples/`, linked but not hosted.
</content>
