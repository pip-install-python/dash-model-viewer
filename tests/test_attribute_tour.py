"""The attribute tour: eleven attributes with no named prop.

Written from an audit against modelviewer.dev's example pages. The value of
this file is mostly that it pins the three things the page could get quietly
wrong: a boolean sent as "false", a dependent attribute sent alone, and the
page claiming to demonstrate something only a phone can show.
"""

from __future__ import annotations

import importlib
import pathlib

import dash_model_viewer as dmv

page = importlib.import_module("docs.attribute-tour.attribute_tour")
REPO = pathlib.Path(__file__).resolve().parent.parent
PAGE_MD = REPO / "docs" / "attribute-tour" / "attribute-tour.md"

#: Every attribute this page exists to cover.
COVERED = [
    "scale", "disable-pan", "disable-tap", "interaction-prompt",
    "skybox-image", "skybox-height", "loading", "reveal",
]
AR_ONLY = ["ar-placement", "xr-environment", "ios-src"]


def _build(**kw):
    args = dict(
        no_pan=False, no_tap=False, no_prompt=False, scale="1 1 1",
        skybox=False, skybox_height=0, loading="auto", reveal="auto",
    )
    args.update(kw)
    viewer, readout = page.rebuild(*args.values())
    return viewer.attributes, readout


# --------------------------------------------------------------------------
# None of these is a named prop — that is the premise
# --------------------------------------------------------------------------


def test_none_of_the_covered_attributes_is_a_named_prop():
    """If one of these ever becomes a prop, this page should shrink, not
    silently keep demonstrating the escape hatch for it."""
    named = {p.replace("_", "-") for p in dmv.ModelViewer._prop_names}
    for attr in COVERED + AR_ONLY:
        assert attr not in named, (
            f"{attr} is now a named prop — move it off this page"
        )


# --------------------------------------------------------------------------
# Booleans: presence, not "false"
# --------------------------------------------------------------------------


def test_boolean_attributes_are_OMITTED_when_off_not_sent_as_false():
    attrs, _ = _build(no_pan=False, no_tap=False)
    assert "disable-pan" not in attrs
    assert "disable-tap" not in attrs


def test_boolean_attributes_are_present_and_empty_when_on():
    attrs, _ = _build(no_pan=True, no_tap=True)
    assert attrs["disable-pan"] == ""
    assert attrs["disable-tap"] == ""


def test_no_attribute_is_ever_sent_as_the_string_false():
    """"false" is a present value, so it turns a boolean attribute ON. This is
    the single most common way an attributes dict does the opposite of what it
    reads like."""
    for kw in ({}, dict(no_pan=True), dict(no_tap=True), dict(no_prompt=True),
               dict(skybox=True)):
        attrs, _ = _build(**kw)
        assert "false" not in [str(v).lower() for v in attrs.values()]


# --------------------------------------------------------------------------
# A dependent attribute must not travel alone
# --------------------------------------------------------------------------


def test_skybox_height_is_not_sent_without_a_skybox():
    """Alone it does nothing. Sending it anyway would put a line in the readout
    that has no effect, which teaches the reader something false."""
    attrs, _ = _build(skybox=False, skybox_height=5)
    assert "skybox-height" not in attrs


def test_skybox_height_is_sent_with_units_when_it_applies():
    attrs, _ = _build(skybox=True, skybox_height=2)
    assert attrs["skybox-height"] == "2m", "model-viewer needs a unit"


def test_a_zero_height_is_not_sent():
    attrs, _ = _build(skybox=True, skybox_height=0)
    assert "skybox-height" not in attrs


# --------------------------------------------------------------------------
# The remount, which is the page's one unusual choice
# --------------------------------------------------------------------------


def test_the_viewer_id_survives_the_rebuild():
    """The page remounts so `loading` and `reveal` are observable. If the id
    changed, anything keyed on it would silently stop working."""
    first, _ = page.rebuild(False, False, False, "1 1 1", False, 0, "auto", "auto")
    second, _ = page.rebuild(True, True, True, "2 2 2", True, 2, "eager", "interaction")
    assert first.id == second.id == "at-viewer"


def test_loading_and_reveal_always_reach_the_element():
    """They are the reason the page remounts; they must not be conditional."""
    for loading in ("auto", "lazy", "eager"):
        for reveal in ("auto", "interaction"):
            attrs, _ = _build(loading=loading, reveal=reveal)
            assert attrs["loading"] == loading
            assert attrs["reveal"] == reveal


def test_the_readout_shows_booleans_without_an_equals_sign():
    _attrs, readout = _build(no_pan=True)
    assert "disable-pan" in readout
    assert 'disable-pan="' not in readout, "a bare boolean should read as bare"


# --------------------------------------------------------------------------
# Honesty about what cannot be shown
# --------------------------------------------------------------------------


def _prose():
    text = PAGE_MD.read_text(encoding="utf-8").replace("*", "").replace("`", "")
    return " ".join(text.split()).lower()


def test_the_page_does_not_pretend_to_demonstrate_the_ar_only_attributes():
    prose = _prose()
    assert "what you cannot see from a laptop" in prose
    for attr in AR_ONLY:
        assert attr in prose, f"{attr} is not listed"


def test_the_ar_only_attributes_are_not_wired_to_a_control_on_THIS_page():
    """Offering a desktop toggle for something only a phone can show is a trap.

    `ar-placement` and `xr-environment` ARE set on /augmented-reality, where a
    phone walk can verify them — see the test below. This asserts only that
    they are not given a control here, which would demonstrate nothing.
    """
    source = (REPO / "docs" / "attribute-tour" / "attribute_tour.py").read_text()
    for attr in AR_ONLY:
        assert attr not in source, f"{attr} is wired to a control it cannot demonstrate"


def test_the_phone_verifiable_ones_are_set_where_a_phone_walk_finds_them():
    """Documented-with-values is weaker than set-and-walkable. Two of the three
    can be set on a real AR page; `ios-src` cannot, because it needs a `.usdz`
    this repo does not ship and pointing it at a missing file would BREAK iOS
    AR in order to document an attribute."""
    ar = (REPO / "docs" / "augmented-reality" / "ar_viewer.py").read_text()
    assert '"ar-placement": "floor"' in ar
    assert '"xr-environment": ""' in ar
    assert "ios-src" not in ar.split("attributes=")[1][:200], (
        "ios-src must not be set without a real .usdz asset"
    )


def test_reveal_manual_is_excluded_and_the_page_says_why():
    """`reveal="manual"` needs dismissPoster(), an imperative method 1.0.0 does
    not expose — offering it would produce a viewer that never reveals."""
    source = (REPO / "docs" / "attribute-tour" / "attribute_tour.py").read_text()
    assert '"manual"' not in source and "'manual'" not in source
    prose = _prose()
    assert "dismissposter()" in prose
    assert "imperative" in prose
