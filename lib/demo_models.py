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

#: 7.8 MB. Carries three GLTF material variants, which is what makes it the
#: only sensible choice for the `variant_name` / `model_info["variants"]`
#: example.
SHOE = f"{_KHRONOS}/MaterialsVariantsShoe/glTF-Binary/MaterialsVariantsShoe.glb"

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

#: Rendered on the credits page. CC BY 4.0 requires attribution, so this is a
#: licence obligation, not a courtesy.
ATTRIBUTION = {
    ASTRONAUT: "Astronaut — Google, model-viewer shared assets",
    ROBOT: "Robot Expressive — Tomás Laulhé, modified by Don McCurdy (CC0)",
    ODD_SHAPE: "Odd shape (labeled) — Google, model-viewer shared assets",
    SHOE: "Materials Variants Shoe — © 2021 Shopify, CC BY 4.0, "
          "via Khronos glTF Sample Assets",
}
