#!/usr/bin/env python3
"""Re-vendor Google's `<model-viewer>` bundle into the package.

    python scripts/vendor_model_viewer.py            # the pinned version
    python scripts/vendor_model_viewer.py 4.4.0      # a different one

Writes `dash_model_viewer/vendor/model-viewer-umd.min.js` and its LICENSE, and
updates `MODEL_VIEWER_VERSION` in `dash_model_viewer/__init__.py`.

WHY A SCRIPT AND NOT A MANUAL DOWNLOAD
--------------------------------------
Because the file is not copied byte-for-byte, and an undocumented hand-edit to
a 1 MB vendored blob is invisible forever. Exactly one modification is made,
and it is made here so it is reproducible and reviewable:

**The trailing `//# sourceMappingURL=` comment is removed.**

Upstream's minified bundle ends with a pointer to `model-viewer-umd.min.js.map`.
Any browser with devtools open follows that pointer, which becomes a request for
`/_dash-component-suites/dash_model_viewer/vendor/model-viewer-umd.min.js.map`.
That path is not in `registered_paths`, so Dash raises `DependencyException` and
the request 500s with a full stack trace in the server log — on every page view,
for every developer, for a file that is only ever wanted by devtools.

The alternatives were worse:

* **Ship the map.** It is 4.7 MB — four times the bundle — in every wheel.
* **Register the path without the file.** Dash would then try to open a file
  that is not there and 500 anyway, just from a different line.
* **Leave it.** A 500 that appears only when devtools are open is precisely the
  kind of defect that gets rediscovered every six months.

Removing the comment costs a debugging affordance nobody has for a minified
third-party bundle regardless, and `tests/test_components.py` asserts it stays
removed.
"""
from __future__ import annotations

import re
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = REPO_ROOT / "dash_model_viewer" / "vendor"
INIT_PY = REPO_ROOT / "dash_model_viewer" / "__init__.py"

BUNDLE_URL = "https://unpkg.com/@google/model-viewer@{v}/dist/model-viewer-umd.min.js"
LICENSE_URL = "https://unpkg.com/@google/model-viewer@{v}/LICENSE"

SOURCEMAP_COMMENT = re.compile(rb"\n?//# sourceMappingURL=[^\n]*\n?$")


def _current_pin() -> str:
    match = re.search(r'^MODEL_VIEWER_VERSION = "([^"]+)"', INIT_PY.read_text(), re.M)
    if not match:
        raise SystemExit("could not read MODEL_VIEWER_VERSION from __init__.py")
    return match.group(1)


def _fetch(url: str, attempts: int = 4) -> bytes:
    """GET with retries, and verify the body is complete.

    unpkg truncates under load often enough to matter: a short read here would
    otherwise write a corrupt 1 MB bundle into the package, and the failure
    would surface as "the model sometimes doesn't render" rather than as a
    download error. Content-Length is checked because `IncompleteRead` is not
    always raised — a truncated response can read clean and short.
    """
    last = None
    for attempt in range(1, attempts + 1):
        try:
            print(f"  GET {url}" + (f"  (attempt {attempt})" if attempt > 1 else ""))
            with urllib.request.urlopen(url, timeout=120) as response:
                declared = response.headers.get("Content-Length")
                body = response.read()
            if declared is not None and len(body) != int(declared):
                raise OSError(
                    f"short read: got {len(body):,} of {int(declared):,} bytes"
                )
            return body
        except Exception as exc:  # noqa: BLE001 - retry anything transport-shaped
            last = exc
            print(f"    {type(exc).__name__}: {exc}")
            time.sleep(2 * attempt)
    raise SystemExit(f"giving up on {url}: {last}")


def main(argv: list[str]) -> int:
    version = argv[1] if len(argv) > 1 else _current_pin()
    print(f"vendoring @google/model-viewer@{version}")

    bundle = _fetch(BUNDLE_URL.format(v=version))
    licence = _fetch(LICENSE_URL.format(v=version))

    if b"customElements.define" not in bundle:
        raise SystemExit("that does not look like the model-viewer bundle")

    stripped, count = SOURCEMAP_COMMENT.subn(b"\n", bundle)
    if count:
        print("  removed the trailing sourceMappingURL comment (see module docstring)")
    else:
        print("  no sourceMappingURL comment found — upstream may have changed")

    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    (VENDOR_DIR / "model-viewer-umd.min.js").write_bytes(stripped)
    (VENDOR_DIR / "model-viewer-LICENSE").write_bytes(licence)

    init = INIT_PY.read_text()
    init = re.sub(
        r'^MODEL_VIEWER_VERSION = "[^"]+"',
        f'MODEL_VIEWER_VERSION = "{version}"',
        init,
        count=1,
        flags=re.M,
    )
    INIT_PY.write_text(init)

    print(f"  wrote {len(stripped):,} bytes (upstream {len(bundle):,})")
    print(f"  MODEL_VIEWER_VERSION = {version}")
    print("\nNow: rerun the tests, and note the version bump in CHANGELOG.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
