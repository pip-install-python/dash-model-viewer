"""One place for the rules every `dcc.Upload` on this site obeys.

Three pages take a file from a visitor: /texture-upload paints an image onto a
model, /sculpt-from-image sends one to a vision model, and /model-upload takes
a `.glb` and renders it. They need the same answers
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


#: `.glb` files arrive with whatever media type the operating system guessed —
#: `model/gltf-binary` on a tidy machine, `application/octet-stream` on most,
#: and sometimes nothing at all. So a model upload is identified by its CONTENT
#: rather than by its label: the format begins with a magic number and a version
#: field, and those cannot be wrong about what the file is.
GLB_MAGIC = b"glTF"

#: Only glTF 2.0. Version 1 is a different format with a different chunk layout
#: that `<model-viewer>` does not read, and failing on it with a clear sentence
#: beats handing the viewer something it will silently refuse to draw.
GLB_VERSION = 2

#: 32 MB. Larger than the 3 MB ceiling on GENERATED sculptures because this is
#: somebody else's file and a real scanned or exported asset is routinely tens
#: of megabytes — but still a ceiling, because the bytes make a round trip and
#: become a `data:` URL in the page.
MAX_MODEL_BYTES = 32 * 1024 * 1024


def decode_model(
    contents: Optional[str],
    filename: Optional[str] = None,
    max_bytes: int = MAX_MODEL_BYTES,
) -> Tuple[Optional[bytes], str]:
    """Validate an uploaded `.glb`. Returns `(raw_bytes_or_None, message)`.

    Same shape and the same failure style as `decode_image`: on success the
    message is a human-readable size, on failure it names the rule that was
    broken. The checks are on the bytes, in order — base64, then size, then the
    12-byte header — so a file that is not a GLB at all is told so rather than
    reaching the viewer and quietly failing to appear.
    """
    if not contents:
        return None, ""
    label = filename or "that file"

    try:
        _header, payload = contents.split(",", 1)
    except ValueError:
        return None, f"{label} is not a data URL."

    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        return None, f"{label} is not valid base64 data."

    if len(raw) > max_bytes:
        return None, (
            f"{label} is {len(raw) / 1048576:.1f} MB — "
            f"the cap is {max_bytes / 1048576:.0f} MB."
        )

    if len(raw) < 12 or raw[:4] != GLB_MAGIC:
        return None, (
            f"{label} is not a binary glTF. A `.glb` begins with the four "
            f"bytes `glTF`; this one begins with "
            f"{raw[:4].decode('latin-1')!r}. A `.gltf` JSON file will not "
            f"work here — it points at textures and buffers that were not "
            f"uploaded with it."
        )

    version = int.from_bytes(raw[4:8], "little")
    if version != GLB_VERSION:
        return None, (
            f"{label} is glTF version {version}; this viewer reads version "
            f"{GLB_VERSION}."
        )

    declared = int.from_bytes(raw[8:12], "little")
    if declared != len(raw):
        return None, (
            f"{label} says it is {declared:,} bytes but is {len(raw):,} — "
            f"it is truncated or was modified in transit."
        )

    return raw, f"glTF 2.0, {len(raw) / 1048576:.1f} MB"
