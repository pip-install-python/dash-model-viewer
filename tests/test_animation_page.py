"""The animation page: clips from the model, everything through attributes."""

from __future__ import annotations

import importlib
import pathlib

page = importlib.import_module("docs.animation.animation")
REPO = pathlib.Path(__file__).resolve().parent.parent
PAGE_MD = REPO / "docs" / "animation" / "animation.md"


# --------------------------------------------------------------------------
# The clip list is the model's, not the page's
# --------------------------------------------------------------------------


def test_clips_come_from_model_info_not_a_hardcoded_list():
    """A hardcoded list of Robot Expressive's fourteen names would look
    identical today and break silently the first time `src` changed."""
    source = (REPO / "docs" / "animation" / "animation.py").read_text()
    for clip in ("Dance", "Punch", "ThumbsUp", "WalkJump"):
        assert clip not in source, f"{clip} is hardcoded in the example"
    assert 'info.get("animations")' in source


def test_before_load_it_does_not_claim_there_are_no_clips():
    data, value, status = page.list_animations(None, None)
    assert data == [] and value is None
    assert "loading" in status.lower()
    assert "no animation" not in status.lower()


def test_a_model_with_no_clips_says_so():
    data, value, status = page.list_animations({"animations": []}, None)
    assert data == [] and value is None
    assert "no animation clips" in status


def test_the_clips_fill_the_picker_and_the_first_is_chosen():
    data, value, status = page.list_animations({"animations": ["Idle", "Wave"]}, None)
    assert data == ["Idle", "Wave"]
    assert value == "Idle"
    assert "2 clips" in status and "Wave" in status


def test_a_surviving_choice_is_kept_across_a_reload():
    _data, value, _status = page.list_animations(
        {"animations": ["Idle", "Wave"]}, "Wave"
    )
    assert value == "Wave"


def test_a_stale_choice_falls_back_rather_than_rendering_blank():
    _data, value, _status = page.list_animations(
        {"animations": ["Idle", "Wave"]}, "Moonwalk"
    )
    assert value == "Idle"


# --------------------------------------------------------------------------
# Everything through attributes
# --------------------------------------------------------------------------


def test_the_page_uses_no_imperative_call():
    """1.0.0 ships no imperative surface; this page must not pretend it does."""
    source = (REPO / "docs" / "animation" / "animation.py").read_text()
    for forbidden in ("clientside", ".play()", ".pause()", "currentTime", "timeScale"):
        assert forbidden not in source, f"{forbidden} appears in the example"


def test_playing_sets_autoplay_and_the_clip():
    attrs = page.drive_animation("Wave", 300, True)
    assert attrs["animation-name"] == "Wave"
    assert attrs["autoplay"] == ""
    assert attrs["animation-crossfade-duration"] == "300"


def test_pausing_adds_the_paused_attribute():
    attrs = page.drive_animation("Wave", 300, False)
    assert attrs["paused"] == ""


def test_resuming_OMITS_paused_rather_than_setting_it_false():
    """`paused` is a boolean attribute — true by PRESENCE. `paused="false"` is
    still paused, so resuming has to leave the key out entirely. The shim
    removes any attribute that disappears between renders."""
    attrs = page.drive_animation("Wave", 300, True)
    assert "paused" not in attrs, (
        'resuming must omit `paused`; setting it to "false" would stay paused'
    )


def test_crossfade_of_zero_is_passed_through_not_dropped():
    """0 is a meaningful value — a hard cut — and falsy, which is exactly the
    shape that gets lost to an `if value:` somewhere."""
    attrs = page.drive_animation("Wave", 0, True)
    assert attrs["animation-crossfade-duration"] == "0"


def test_no_clip_yet_makes_no_change():
    from dash import no_update

    assert page.drive_animation(None, 300, True) is no_update


# --------------------------------------------------------------------------
# The page's claims
# --------------------------------------------------------------------------


def _prose():
    text = PAGE_MD.read_text(encoding="utf-8").replace("*", "").replace("`", "")
    return " ".join(text.split())


def test_the_page_states_what_is_NOT_possible():
    """Scrubbing and speed are JS-only in 1.0.0. Saying so beats letting
    someone hunt for a prop that does not exist."""
    prose = _prose().lower()
    assert "no scrubbing and no speed control" in prose
    assert "currenttime" in prose and "timescale" in prose


def test_the_page_explains_the_boolean_attribute_trap():
    assert "true by presence" in _prose().lower()


def test_the_page_does_not_overstate_which_models_animate():
    prose = _prose().lower()
    assert "only robot expressive has animations" in prose
