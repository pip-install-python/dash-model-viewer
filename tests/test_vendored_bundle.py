"""The vendored bundle as the SITE serves it, and the script that makes it.

Site lane only. tests/test_components.py pins the same strings on the
package's own file, because that file runs in the wheel-only package lane
and can use neither the `client` fixture nor the repo's `scripts/`.
"""

from __future__ import annotations

import importlib.util
import re

import pytest

from conftest import REPO_ROOT
from test_components import DEBUG_LOG_STRINGS


def _served_bundle(client) -> bytes:
    """The bundle as Dash SERVES it — found from the index, fetched by URL."""
    index = client.get("/").text
    urls = re.findall(r'src="([^"]*model-viewer-umd[^"]*)"', index)
    assert len(urls) == 1, urls
    response = client.get(urls[0])
    assert response.status == 200, (urls[0], response.status)
    body = response.text.encode("utf-8")
    assert len(body) > 500_000, "not the bundle — the corpus must be the real file"
    return body


@pytest.mark.parametrize("needle", DEBUG_LOG_STRINGS)
def test_the_served_bundle_carries_none_of_upstreams_debug_logs(client, needle):
    assert needle not in _served_bundle(client), (
        f"{needle!r} is back in the served bundle — re-vendor with "
        "scripts/vendor_model_viewer.py rather than by hand"
    )


def test_the_served_bundle_keeps_the_behaviour_the_logs_sat_in(client):
    served = _served_bundle(client)
    assert b"this.loaded||!this[EE]()||this.src===t.url&&i)return;" in served
    assert b"this[iE]=e.isIntersecting,this[nE](t),this[iE]&&" in served
    assert served.count(b"console.log(") == 10


def test_the_vendor_script_refuses_a_bundle_it_cannot_patch_exactly():
    """A version whose minified text differs must fail loudly, not ship the
    logs or a half-edited bundle."""
    spec = importlib.util.spec_from_file_location(
        "vendor_model_viewer", REPO_ROOT / "scripts" / "vendor_model_viewer.py"
    )
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)

    with pytest.raises(SystemExit, match="found 0"):
        script.strip_debug_logs(b"customElements.define(no logs here)")
    doubled = b"".join(n for n, _ in script.DEBUG_LOGS) * 2
    with pytest.raises(SystemExit, match="found 2"):
        script.strip_debug_logs(doubled)
    once = b"".join(n for n, _ in script.DEBUG_LOGS)
    assert script.strip_debug_logs(once) == b"return;"
