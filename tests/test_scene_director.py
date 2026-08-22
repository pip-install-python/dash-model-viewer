"""The Scene Director's guardrails — none of these call the API.

`conftest.py` blanks ANTHROPIC_API_KEY before anything imports the app, so a
test run can never spend money. That is asserted here too, because it is the
kind of protection that gets deleted by someone tidying an env list.

Everything worth testing in this feature is the code either side of the API
call: the grounding that goes in, and the clamping and sanitising that come
out. Those are pure functions.
"""

from __future__ import annotations

import os

import pytest

from lib import scene_director as sd

INFO = {
    "dimensions": {"x": 0.294, "y": 0.148, "z": 0.104},  # the Khronos shoe
    "variants": ["midnight", "beach", "street"],
    "animations": [],
}


# --------------------------------------------------------------------------
# Cost posture
# --------------------------------------------------------------------------


def test_the_suite_cannot_spend_money():
    """`lib/backend.py` calls load_dotenv(), so a real .env key would leak in."""
    assert not os.environ.get("ANTHROPIC_API_KEY"), (
        "conftest.py must blank ANTHROPIC_API_KEY — otherwise the suite bills "
        "the developer's own account on every run"
    )
    assert sd.available() is False


def test_no_key_fails_closed_with_an_explanation():
    result = sd.generate("anything", model_info=INFO)
    assert result.ok is False
    assert "ANTHROPIC_API_KEY" in result.reason
    assert result.props == {}


def test_empty_and_oversized_requests_are_refused_before_the_api():
    assert sd.generate("", model_info=INFO).ok is False
    assert sd.generate("x" * 501, model_info=INFO).ok is False


def test_missing_dimensions_refuses_rather_than_guessing(monkeypatch):
    """Without a measured bounding box the whole grounding argument collapses.

    `available()` is faked rather than the key set: the no-key branch runs
    first (deliberately — "no key" is the more useful message when there is no
    key at all), so this guard is only reachable on a configured host.
    """
    monkeypatch.setattr(sd, "available", lambda: True)
    result = sd.generate("a dramatic angle", model_info={"dimensions": None})
    assert result.ok is False
    assert "dimensions" in result.reason


# --------------------------------------------------------------------------
# Grounding
# --------------------------------------------------------------------------


def test_the_prompt_carries_the_measured_geometry():
    prompt = sd._system_prompt(INFO, {"orbit": "15deg 78deg 0.42m"})
    assert "0.294" in prompt and "0.148" in prompt
    assert "midnight" in prompt
    # The radius window is derived from the model, not hard-coded.
    assert "0.24m" in prompt and "0.88m" in prompt


def test_the_prompt_survives_a_model_that_has_not_loaded():
    prompt = sd._system_prompt({}, None)
    assert "not yet reported" in prompt


# --------------------------------------------------------------------------
# Clamping — shape is not sanity
# --------------------------------------------------------------------------


def test_radius_inside_the_mesh_is_pushed_out():
    scene, notes = sd._clamp({"camera_orbit": "40deg 118deg 0.01m"}, INFO)
    radius = float(scene["camera_orbit"].split()[2].rstrip("m"))
    assert radius >= 0.294 * 0.8
    assert any("radius clamped" in n for n in notes)


def test_a_camera_a_kilometre_away_is_pulled_in():
    scene, notes = sd._clamp({"camera_orbit": "0deg 90deg 1000m"}, INFO)
    radius = float(scene["camera_orbit"].split()[2].rstrip("m"))
    assert radius <= 0.294 * 3.0
    assert any("radius clamped" in n for n in notes)


@pytest.mark.parametrize("phi", ["0", "180", "-20", "400"])
def test_pole_angles_are_clamped(phi):
    scene, notes = sd._clamp({"camera_orbit": f"0deg {phi}deg 0.4m"}, INFO)
    value = float(scene["camera_orbit"].split()[1].rstrip("deg"))
    assert 10 <= value <= 170
    assert any("phi clamped" in n for n in notes)


def test_units_are_normalised():
    """`40cm` is a plausible thing to emit and would otherwise read as 40 metres."""
    scene, _ = sd._clamp({"camera_orbit": "0deg 90deg 40cm"}, INFO)
    radius = float(scene["camera_orbit"].split()[2].rstrip("m"))
    assert 0.3 < radius < 0.5


def test_unparseable_values_are_discarded_not_guessed():
    scene, notes = sd._clamp(
        {"camera_orbit": "somewhere nice", "camera_target": "over there"}, INFO
    )
    assert "camera_orbit" not in scene
    assert "camera_target" not in scene
    assert len(notes) == 2


def test_a_variant_the_file_does_not_have_falls_back():
    scene, notes = sd._clamp({"variant_name": "chartreuse"}, INFO)
    assert scene["variant_name"] is None
    assert any("chartreuse" in n for n in notes)


def test_a_real_variant_survives():
    scene, notes = sd._clamp({"variant_name": "midnight"}, INFO)
    assert scene["variant_name"] == "midnight"
    assert notes == []


def test_shadow_intensity_is_bounded():
    assert sd._clamp({"shadow_intensity": 9}, INFO)[0]["shadow_intensity"] == 1.0
    assert sd._clamp({"shadow_intensity": -3}, INFO)[0]["shadow_intensity"] == 0.0
    assert "shadow_intensity" not in sd._clamp({"shadow_intensity": "lots"}, INFO)[0]


def test_an_invented_tone_mapping_is_dropped():
    assert "tone_mapping" not in sd._clamp({"tone_mapping": "cinematic"}, INFO)[0]


# --------------------------------------------------------------------------
# Sanitising — this one is a security boundary
# --------------------------------------------------------------------------


@pytest.mark.parametrize("attr", sorted(sd.BLOCKED_ATTRIBUTES))
def test_model_output_may_never_choose_what_the_browser_fetches(attr):
    """Every blocked attribute points the browser at a URL."""
    scene, notes = sd._clamp(
        {"attributes": [{"name": attr, "value": "https://evil.example/x.glb"}]}, INFO
    )
    assert attr not in scene["attributes"]
    assert any(attr in n for n in notes)


def test_harmless_attributes_pass_through():
    scene, _ = sd._clamp(
        {
            "attributes": [
                {"name": "exposure", "value": "1.2"},
                {"name": "Shadow-Softness", "value": "0.4"},
            ]
        },
        INFO,
    )
    assert scene["attributes"] == {"exposure": "1.2", "shadow-softness": "0.4"}


def test_attributes_cannot_shadow_the_named_camera_props():
    """Otherwise the clamped orbit could be overridden by an unclamped one."""
    scene, _ = sd._clamp(
        {
            "camera_orbit": "0deg 90deg 0.4m",
            "attributes": [{"name": "camera-orbit", "value": "0deg 0deg 9999m"}],
        },
        INFO,
    )
    assert "camera-orbit" not in scene["attributes"]
    assert scene["camera_orbit"] == "0deg 90deg 0.40m"


def test_the_schema_has_no_free_form_map():
    """Structured outputs reject `additionalProperties` as anything but false.

    A dict-valued `attributes` field is therefore inexpressible, and the API
    returns a 400 rather than degrading. The open key space is modelled as a
    list of {name, value} pairs instead.
    """
    schema = sd._schema()
    attributes = schema["properties"]["attributes"]
    assert attributes["type"] == "array"
    assert attributes["items"]["additionalProperties"] is False
    assert schema["additionalProperties"] is False
