"""Demo models used by the documentation examples.

Every model here is published by Google (as `<model-viewer>`'s own shared
assets) or by the Khronos Group (the glTF Sample Assets repository), under
licences that permit exactly this use. That is deliberate and it is not a
detail: a docs site is public and indexed, so an unattributed third-party
character model is a takedown waiting to happen rather than a tidiness issue.

**Do not add a model here without checking its licence**, and do not reach for
the `.glb` files still sitting in this repository's `assets/` directory — they
came from the 0.0.1 examples and at least two are commercial game characters.

Hot-linking upstream keeps ~25 MB of binaries out of the repo and off the free
tier's bandwidth. The production step is to mirror these onto cdn.2plot.ai and
flip `CDN_BASE`; the URLs are centralised here so that is a one-line change
rather than a sweep through nine markdown files.
"""

from __future__ import annotations

# Google's model-viewer shared assets — Apache-2.0, published as samples.
_MV = "https://modelviewer.dev/shared-assets/models"

# Khronos glTF Sample Assets — see each model's own LICENSE.md in that repo.
_KHRONOS = (
    "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models"
)

#: 2.8 MB. The canonical model-viewer demo; good hotspot geometry.
ASTRONAUT = f"{_MV}/Astronaut.glb"

#: 464 KB, rigged and animated. The lightest model that still looks like
#: something, so it is the default for pages that are about a *prop* rather
#: than about the model.
ROBOT = f"{_MV}/RobotExpressive.glb"

#: 363 KB, with labelled faces — the clearest way to show that reported
#: dimensions correspond to something real.
ODD_SHAPE = f"{_MV}/odd-shape-labeled.glb"

#: 7.5 MB. Three GLTF material variants — `midnight`, `beach`, `street`.
#: The canonical `variant_name` / `model_info["variants"]` demo.
SHOE = f"{_KHRONOS}/MaterialsVariantsShoe/glTF-Binary/MaterialsVariantsShoe.glb"

# ---------------------------------------------------------------------------
# Models that CARRY MATERIAL VARIANTS.
#
# The variant list beside each one was MEASURED, not assumed: an HTTP Range
# request for the GLB's JSON chunk, read for `KHR_materials_variants`. Fifteen
# Khronos sample models were probed and only five carry the extension, which is
# why /model-switching used to offer three models of which exactly one could
# demonstrate the feature the page is named after.
# ---------------------------------------------------------------------------

#: 3.0 MB, FIVE variants — `Champagne`, `Navy`, `Gray`, `Black`, `Pale Pink`.
#: The best variants demo in the sample set: the most variants, the smallest
#: download, and a colour change obvious at a glance.
GLAM_SOFA = f"{_KHRONOS}/GlamVelvetSofa/glTF-Binary/GlamVelvetSofa.glb"

#: 3.9 MB, two variants — `Mango Velvet`, `Peacock Velvet`. Also carries
#: `KHR_materials_sheen`, so the variant swap changes the sheen too.
SHEEN_CHAIR = f"{_KHRONOS}/SheenChair/glTF-Binary/SheenChair.glb"

# ---------------------------------------------------------------------------
# Models for VARIETY, so the docs stop showing the same astronaut on every
# page. None of these carry variants; do not put them on /model-switching.
# ---------------------------------------------------------------------------

#: 8.5 MB. Subsurface scattering — light passes through thin bone, which is a
#: material behaviour none of the other demo models show.
SKULL = f"{_KHRONOS}/ScatteringSkull/glTF-Binary/ScatteringSkull.glb"

#: 2.6 MB. Physically-based transparency and refraction. The smallest model
#: here and the only one that shows glass.
CANDLE_GLASS = (
    f"{_KHRONOS}/GlassHurricaneCandleHolder/glTF-Binary/"
    "GlassHurricaneCandleHolder.glb"
)

# NOT ADDED, and recorded rather than silently omitted — the licences were
# read before adding, as the warning at the top of this file requires:
#
#   * VirtualCity — 3DRT's "License for Testing", whose text grants the licence
#     "only if you have paid the applicable fee" and reserves the right to
#     revoke it. A public documentation site carrying an ad client is not
#     glTF testing. Same reasoning as DamagedHelmet below.
#   * DamagedHelmet — see the note above; the owner reaffirmed the exclusion
#     on 2026-09-10 when it came up again as a reference showcase's default.
#   * DragonAttenuation — has variants (`Attenuation`, `Surface Color`), but
#     the dragon is under the Stanford Graphics Library licence, a bespoke
#     grant rather than a Creative Commons one. Not read in full, so not used:
#     an unread licence is not a permission.
#   * MosquitoInAmber (23.1 MB), AntiqueCamera (16.7 MB), Corset (12.9 MB),
#     BarramundiFish (11.9 MB) — licences not checked, because the size rules
#     them out for a docs page regardless.

# NOT used, and deliberately recorded rather than silently omitted:
# Khronos' DamagedHelmet is the obvious "dense PBR materials" demo, but its
# README credits an earlier version under CC BY-NC 4.0. This site carries an
# ad client, so "non-commercial" is not a safe assumption to make about it.
# Three.js' Horse.glb was dropped for the weaker reason that its licence is
# not stated where it is served from.

#: An HDR environment, for the `attributes` / `mv_*` parity page.
MOON_HDR = "https://modelviewer.dev/shared-assets/environments/moon_1k.hdr"

#: Poster images keep a cold page from showing an empty box while several
#: megabytes download — and on this site every page carries a viewer.
POSTER_ASTRONAUT = "https://modelviewer.dev/assets/poster-astronaut.png"

#: CC BY 4.0 requires attribution, so this is a licence obligation, not a
#: courtesy.
#:
#: CAUTION: nothing imports this dict. The attribution that actually reaches a
#: reader is hand-written prose in `pages/home.md`'s Credits section, so a
#: model added HERE and not THERE is an unmet licence obligation that no test
#: and no import graph will notice. Both were updated together on 2026-09-10;
#: `tests/test_demo_models.py` now fails if they drift apart.
ATTRIBUTION = {
    ASTRONAUT: "Astronaut — Google, model-viewer shared assets",
    ROBOT: "Robot Expressive — Tomás Laulhé, modified by Don McCurdy (CC0)",
    ODD_SHAPE: "Odd shape (labeled) — Google, model-viewer shared assets",
    SHOE: "Materials Variants Shoe — © 2021 Shopify, CC BY 4.0, "
          "via Khronos glTF Sample Assets",
    GLAM_SOFA: "Glam Velvet Sofa — © 2021 Wayfair, LLC (Eric Chadwick), "
               "CC BY 4.0, via Khronos glTF Sample Assets",
    SHEEN_CHAIR: "Sheen Chair — © 2020 Wayfair, LLC (Eric Chadwick), CC0 1.0, "
                 "via Khronos glTF Sample Assets",
    SKULL: "Scattering Skull — © 2025 Vladimir Petkovic, CC0 1.0, "
           "via Khronos glTF Sample Assets",
    CANDLE_GLASS: "Glass Hurricane Candle Holder — © 2021 Wayfair, LLC "
                  "(Eric Chadwick), CC BY 4.0, via Khronos glTF Sample Assets",
}

#: The subset that carries `KHR_materials_variants`, measured rather than
#: assumed. /model-switching offers exactly these, so every model on that page
#: can demonstrate what the page is about.
MODELS_WITH_VARIANTS = {
    "Sofa": GLAM_SOFA,
    "Chair": SHEEN_CHAIR,
    "Shoe": SHOE,
}
