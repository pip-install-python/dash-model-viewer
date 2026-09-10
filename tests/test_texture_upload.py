"""The texture upload's type and size rules.

`validate_texture` is deliberately a plain function with no Dash imports, so
the rules the page states can be checked without a browser or a running app.
A cap that is documented and not enforced is the shape of defect 1.0.0 spent
its review removing.
"""

from __future__ import annotations

import base64
import importlib
import pathlib

import pytest

texture_upload = importlib.import_module("docs.texture-upload.texture_upload")

validate_texture = texture_upload.validate_texture
MAX = texture_upload.MAX_TEXTURE_BYTES
REPO = pathlib.Path(__file__).resolve().parent.parent


def data_url(media_type: str, raw: bytes) -> str:
    return f"data:{media_type};base64," + base64.b64encode(raw).decode()


# --------------------------------------------------------------------------
# Type
# --------------------------------------------------------------------------


@pytest.mark.parametrize("media_type", ["image/png", "image/jpeg"])
def test_accepted_types_pass(media_type):
    url = data_url(media_type, b"x" * 32)
    accepted, message = validate_texture(url, "swatch")
    assert accepted == url
    assert "applied" in message.lower()


@pytest.mark.parametrize(
    "media_type",
    [
        "image/svg+xml",   # scriptable document, not an image
        "image/gif",
        "image/webp",
        "text/html",
        "application/octet-stream",
    ],
)
def test_rejected_types_are_refused_by_name(media_type):
    accepted, message = validate_texture(data_url(media_type, b"x" * 32), "thing")
    assert accepted is None
    assert media_type in message, "the message should name what was rejected"


def test_svg_is_rejected_even_though_browsers_render_it():
    """Explicit, because rejecting SVG is a decision rather than an oversight."""
    accepted, _ = validate_texture(data_url("image/svg+xml", b"<svg/>"), "x.svg")
    assert accepted is None


# --------------------------------------------------------------------------
# Size
# --------------------------------------------------------------------------


def test_at_the_cap_is_accepted():
    accepted, _ = validate_texture(data_url("image/png", b"x" * MAX), "big")
    assert accepted is not None, "the cap is inclusive"


def test_one_byte_over_the_cap_is_refused():
    accepted, message = validate_texture(
        data_url("image/png", b"x" * (MAX + 1)), "toobig"
    )
    assert accepted is None
    assert "cap" in message.lower()


def test_the_cap_is_measured_on_DECODED_bytes():
    """base64 inflates by ~4/3. Measuring the encoded string would reject
    files a third smaller than the stated cap, so the number on the page
    would be wrong for every upload."""
    raw = b"x" * (MAX - 1024)          # under the cap decoded...
    url = data_url("image/png", raw)
    assert len(url) > MAX, "this test is vacuous unless the ENCODED form is over"
    accepted, _ = validate_texture(url, "near-cap")
    assert accepted is not None


# --------------------------------------------------------------------------
# Malformed input
# --------------------------------------------------------------------------


def test_no_upload_is_not_an_error():
    assert validate_texture(None) == (None, "")


def test_not_a_data_url():
    accepted, message = validate_texture("just a string", "x")
    assert accepted is None and "data URL" in message


def test_bad_base64_is_caught_not_raised():
    accepted, message = validate_texture("data:image/png;base64,!!!not!!!", "x")
    assert accepted is None and "base64" in message


# --------------------------------------------------------------------------
# The page must not contradict the code
# --------------------------------------------------------------------------


def _prose(path: pathlib.Path) -> str:
    """Page text with line wrapping and emphasis flattened.

    Markdown wraps where it likes and bolds what it likes, so a literal
    substring check fails on `**never written to\\ndisk**` — which is the page
    keeping its promise, not breaking it. Normalise rather than force the
    prose into awkward line breaks to satisfy a test.
    """
    text = path.read_text(encoding="utf-8").replace("*", "").replace("`", "")
    return " ".join(text.split()).lower()


def test_the_page_states_the_cap_the_code_enforces():
    page = _prose(REPO / "docs" / "texture-upload" / "texture-upload.md")
    cap_mb = MAX // (1024 * 1024)
    assert f"{cap_mb} mb" in page, (
        f"the page must state the {cap_mb} MB cap that the code enforces"
    )
    for promised in ("never written to disk", "png, jpeg"):
        assert promised in page, f"page no longer promises: {promised}"


def test_nothing_in_the_example_writes_to_disk():
    """The page promises the bytes never touch disk; hold the code to it."""
    source = (REPO / "docs" / "texture-upload" / "texture_upload.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ("open(", "Path(", "write_bytes", "write_text", "NamedTemporary"):
        assert forbidden not in source, (
            f"{forbidden!r} appears in the texture example, which promises the "
            f"upload is never written to disk"
        )
