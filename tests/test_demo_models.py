"""The demo models, their licences, and the two places attribution lives.

`lib/demo_models.py` carries an ATTRIBUTION dict that NOTHING IMPORTS. The
attribution a reader actually sees is hand-written prose in `pages/home.md`.
That split is a licence hazard rather than an untidiness: a CC BY model added
to the dict and not to the page is an unmet obligation, and no import graph,
type checker or existing test would notice. These tests are the thing that
notices.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from lib import demo_models

REPO = pathlib.Path(__file__).resolve().parent.parent
HOME = REPO / "pages" / "home.md"


def _credits_section() -> str:
    text = HOME.read_text(encoding="utf-8")
    start = text.index("## Credits")
    rest = text[start + len("## Credits"):]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def _model_constants() -> dict[str, str]:
    """Every module-level URL constant that points at a model file."""
    return {
        name: value
        for name, value in vars(demo_models).items()
        if name.isupper()
        and isinstance(value, str)
        and value.endswith((".glb", ".gltf"))
    }


def test_there_are_models_to_check():
    """Guard the guard: an empty sweep would make every test below vacuous."""
    models = _model_constants()
    assert len(models) >= 6, f"only found {len(models)} model constants"


def test_every_model_constant_has_an_attribution_entry():
    missing = [
        name for name, url in _model_constants().items()
        if url not in demo_models.ATTRIBUTION
    ]
    assert not missing, (
        f"models with no ATTRIBUTION entry: {missing}. Every model carries a "
        f"licence; several require attribution by name."
    )


@pytest.mark.parametrize(
    "holder",
    ["Shopify", "Wayfair", "Vladimir Petkovic"],
)
def test_credits_page_names_every_rights_holder(holder):
    """The page is the surface that discharges the obligation, not the dict."""
    assert holder in _credits_section(), (
        f"pages/home.md's Credits section does not name {holder!r}. A model "
        f"was added to lib/demo_models.py without updating the only "
        f"attribution a reader ever sees."
    )


def test_cc_by_models_are_attributed_on_the_page_not_only_in_the_dict():
    """CC BY requires attribution; CC0 does not. Check the ones that must."""
    credits = _credits_section()
    for url, text in demo_models.ATTRIBUTION.items():
        if "CC BY" not in text:
            continue
        # The human-readable model name is the part before the em dash.
        name = text.split("—")[0].strip()
        assert name in credits, (
            f"{name!r} is CC BY and is not named in pages/home.md's Credits"
        )


def test_every_variants_model_is_a_known_model():
    for label, url in demo_models.MODELS_WITH_VARIANTS.items():
        assert url in demo_models.ATTRIBUTION, f"{label} is not attributed"


def test_the_variants_page_offers_only_models_that_have_variants():
    """/model-switching is named for a feature only five sample models carry.

    Offering a model without variants there is what made the page look broken:
    two of its three choices could not demonstrate the thing it documents.
    """
    switching = (REPO / "docs" / "model-switching" / "switching.py").read_text(
        encoding="utf-8"
    )
    assert "MODELS_WITH_VARIANTS" in switching, (
        "the switching example should take its model list from "
        "demo_models.MODELS_WITH_VARIANTS rather than assembling its own"
    )
    for excluded in ("ASTRONAUT", "ROBOT", "ODD_SHAPE", "SKULL", "CANDLE_GLASS"):
        assert not re.search(rf"\b{excluded}\b", switching), (
            f"{excluded} carries no material variants and must not be offered "
            f"on /model-switching"
        )


def test_licence_rejections_stay_recorded():
    """The exclusions are decisions; an undocumented one reads as an oversight.

    DamagedHelmet was rejected on CC BY-NC grounds and reaffirmed by the owner
    on 2026-09-10; VirtualCity's 3DRT grant is conditional on a paid fee.
    """
    source = pathlib.Path(demo_models.__file__).read_text(encoding="utf-8")
    for name in ("DamagedHelmet", "VirtualCity", "DragonAttenuation"):
        assert name in source, f"the reason for excluding {name} was dropped"
    for name in ("DamagedHelmet", "VirtualCity"):
        assert name not in str(_model_constants().values()), (
            f"{name} is licence-excluded but is being served"
        )
