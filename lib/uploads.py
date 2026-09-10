"""One place for the rules every `dcc.Upload` on this site obeys.

Two pages take an image from a visitor: /texture-upload paints it onto a model,
and /sculpt-from-image sends it to a vision model. They need the same answers
to the same questions — which types, how big, and what happens to the bytes —
and two copies of those answers is two places for them to drift apart. The
second page is where a duplicated cap silently becomes a different cap.

NOTHING HERE TOUCHES DISK. The bytes are decoded to be MEASURED and then
dropped. Both pages say so in prose, and their tests hold the code to it.
"""

from __future__ import annotations

import base64
import binascii
from typing import Dict, Optional, Tuple

#: Raster formats a browser decodes without a plugin and a vision model
#: accepts. SVG is deliberately absent from every caller: it is a scriptable
#: document, not an image.
IMAGE_TYPES: Dict[str, str] = {"image/png": "PNG", "image/jpeg": "JPEG"}


def decode_image(
    contents: Optional[str],
    filename: Optional[str] = None,
    max_bytes: int = 4 * 1024 * 1024,
    accepted: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[bytes], str, str]:
    """Validate a `dcc.Upload` value.

    Returns `(raw_bytes_or_None, media_type, message)`. On success `message` is
    a human-readable size; on failure it says which rule was broken and names
    what was rejected, because "invalid file" tells a user nothing about how to
    succeed on the next try.

    Pure and Dash-free, so the rules are testable without a browser.
    """
    accepted = accepted or IMAGE_TYPES
    if not contents:
        return None, "", ""
    label = filename or "that file"

    try:
        header, payload = contents.split(",", 1)
    except ValueError:
        return None, "", f"{label} is not a data URL."

    media_type = header[5:].split(";")[0].lower() if header.startswith("data:") else ""
    if media_type not in accepted:
        names = " or ".join(sorted(accepted.values()))
        return None, media_type, (
            f"{label} is {media_type or 'of unknown type'} — {names} only."
        )

    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        return None, media_type, f"{label} is not valid base64 image data."

    # Measured on the DECODED bytes. base64 inflates by 4/3, so checking the
    # encoded string would reject files a third smaller than the stated cap and
    # make every page's published number wrong.
    if len(raw) > max_bytes:
        return None, media_type, (
            f"{label} is {len(raw) / 1048576:.1f} MB — "
            f"the cap is {max_bytes / 1048576:.0f} MB."
        )

    return raw, media_type, f"{accepted[media_type]}, {len(raw) / 1024:.0f} KB"
