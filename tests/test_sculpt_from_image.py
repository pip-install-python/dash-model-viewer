"""The generative image page: upload rules, the honesty claim, and the gate.

No model is called anywhere here. The vision request is mocked, so these run
with no key, no network and no spend.
"""

from __future__ import annotations

import base64
import importlib
import pathlib
from unittest import mock

import pytest

from lib import sculptor, uploads

page = importlib.import_module("docs.sculpt-from-image.sculpt_from_image")
REPO = pathlib.Path(__file__).resolve().parent.parent
PAGE_MD = REPO / "docs" / "sculpt-from-image" / "sculpt-from-image.md"


def data_url(media_type: str, raw: bytes) -> str:
    return f"data:{media_type};base64," + base64.b64encode(raw).decode()


# --------------------------------------------------------------------------
# Upload rules — shared with /texture-upload, so they cannot drift
# --------------------------------------------------------------------------


def test_the_two_upload_pages_share_one_rulebook():
    """A second page taking an image is where a duplicated cap silently
    becomes a different cap."""
    texture = importlib.import_module("docs.texture-upload.texture_upload")
    assert texture.ACCEPTED_TYPES is uploads.IMAGE_TYPES
    assert page.MAX_IMAGE_BYTES == texture.MAX_TEXTURE_BYTES


@pytest.mark.parametrize("media_type", ["image/png", "image/jpeg"])
def test_accepted_types_enable_the_button(media_type):
    stored, message, preview, disabled = page.accept_image(
        data_url(media_type, b"x" * 64), "shot"
    )
    assert stored is not None and disabled is False
    assert "ready" in message


@pytest.mark.parametrize("media_type", ["image/svg+xml", "image/gif", "text/html"])
def test_rejected_types_keep_the_button_disabled_and_name_the_type(media_type):
    stored, message, _preview, disabled = page.accept_image(
        data_url(media_type, b"x" * 64), "thing"
    )
    assert stored is None and disabled is True
    assert media_type in message


def test_over_the_cap_is_refused_on_decoded_bytes():
    stored, message, _p, disabled = page.accept_image(
        data_url("image/png", b"x" * (page.MAX_IMAGE_BYTES + 1)), "big"
    )
    assert stored is None and disabled is True and "cap" in message


def test_nothing_in_the_page_writes_to_disk():
    source = (REPO / "docs" / "sculpt-from-image" / "sculpt_from_image.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ("open(", "write_bytes", "write_text", "NamedTemporary"):
        assert forbidden not in source, f"{forbidden!r} appears in the page"


# --------------------------------------------------------------------------
# The claim the page makes about itself
# --------------------------------------------------------------------------


def _prose(path: pathlib.Path) -> str:
    text = path.read_text(encoding="utf-8").replace("*", "").replace("`", "")
    return " ".join(text.split()).lower()


def test_the_page_says_plainly_that_it_is_not_a_reconstruction():
    """The owner asked for image->3D; a visitor will reasonably expect their
    object back. Saying so is the difference between a feature and a
    disappointment."""
    prose = _prose(PAGE_MD)
    assert "interpretation, not a reconstruction" in prose
    assert "not your car" in prose
    for absent in ("photogrammetry", "depth estimation", "mesh fitting"):
        assert absent in prose, f"the page should disclaim {absent}"


def test_the_page_discloses_that_the_image_leaves_the_browser():
    """This is the row that differs from /texture-upload, where the image
    never leaves the tab."""
    prose = _prose(PAGE_MD)
    assert "sent to a third party" in prose
    assert "anthropic or openai" in prose


def test_the_page_points_at_the_deterministic_alternative():
    prose = _prose(PAGE_MD)
    assert "/image-to-3d" in prose
    assert "needs no api key" in prose


def test_the_system_prompt_actually_asks_for_interpretation():
    """The prose promises it; the prompt has to deliver it."""
    assert "EVOKES" in sculptor.IMAGE_SYSTEM
    assert "not reconstructing" in sculptor.IMAGE_SYSTEM
    for refused in ("text", "faces"):
        assert refused in sculptor.IMAGE_SYSTEM


# --------------------------------------------------------------------------
# The gate and the single call
# --------------------------------------------------------------------------


def test_no_image_is_refused_before_any_spend():
    with mock.patch.object(sculptor.spend, "record") as record:
        result = sculptor.sculpt_image("", enforce_budget=False)
    assert result.ok is False and "Upload an image" in result.reason
    record.assert_not_called()


def test_the_budget_gate_runs_before_the_model(monkeypatch):
    monkeypatch.setattr(
        sculptor.spend, "check",
        lambda *a, **k: sculptor.spend.Verdict(False, "Spend ceiling reached."),
    )
    result = sculptor.sculpt_image(data_url("image/png", b"x"), enforce_budget=True)
    assert result.ok is False and "Spend ceiling" in result.reason


def test_a_missing_key_is_reported_not_raised(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = sculptor.sculpt_image(
        data_url("image/png", b"x"), enforce_budget=False
    )
    assert result.ok is False and "ANTHROPIC_API_KEY" in result.reason


def test_the_openai_path_sends_the_image_with_the_prompt(monkeypatch):
    """The picture must actually reach the model — a vision page that posts
    only text would return a plausible sculpture of nothing in particular."""
    monkeypatch.setenv("CHATGPT_API_KEY", "k")
    captured = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return {"name": "x", "notes": "", "parts": []}, {
            "input_tokens": 1, "output_tokens": 1}, "stop"

    monkeypatch.setattr(sculptor.openai_client, "complete_json", fake)
    url = data_url("image/png", b"x" * 8)
    sculptor.sculpt_image(url, hint="lean into the arches",
                          model="gpt-6-astra", enforce_budget=False)
    assert captured["image_data_url"] == url
    assert "arches" in captured["prompt"]
    assert "EVOKES" in captured["system"]


def test_streaming_from_an_image_charges_once(monkeypatch):
    """Same rule as the text path: emitting per part is not charging per part."""
    from lib import build_stream

    calls = []
    monkeypatch.setattr(sculptor.spend, "record", lambda *a, **k: calls.append(a) or 0.0)
    monkeypatch.setattr(
        sculptor, "sculpt_image",
        lambda *a, **k: sculptor.SculptResult(
            ok=True, manifest={"name": "x", "notes": "", "parts": []}, part_count=0
        ),
    )
    run = build_stream.new_run()
    sculptor.sculpt_image_streaming(run, data_url("image/png", b"x"))
    assert calls == [], "the streaming layer must meter nothing of its own"
