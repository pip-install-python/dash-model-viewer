"""Network bulletin — hub-published tips and announcements.

TEMPLATE FILE: satellites copy this verbatim; only the env values differ.

The hub (2plot.dev) serves one JSON document at ``/api/network/bulletin`` and
every satellite renders it in the header of its llms.txt viewer. That is the
whole point: a twenty-site network says "here is what changed" once, in one
place, instead of in twenty repositories that immediately drift.

WHY THIS FILE EXISTS RATHER THAN FOUR LINES IN run.py
-----------------------------------------------------
It was four lines in ``run.py``, and they were **commented out** — with a note
saying the hub did not serve the endpoint yet. The hub started serving it, the
comment did not change, and `NETWORK_BULLETIN_URL` was set in production for a
while against code that never read it. Nothing failed: `configure_bulletin`
is opt-in, so an unwired app makes no request and the viewer header renders
perfectly well with the package's built-in defaults. The only symptom was an
announcement that never appeared, which is not a symptom anyone notices.

So the wiring is a function that returns whether it wired, `run.py` prints
that, and `tests/test_bulletin.py` exercises it directly — no commented-out
code, and a boot log line that says which of the two states you are in.

Env:
    NETWORK_BULLETIN_URL   the hub endpoint. Absent -> feature off, silently.
    NETWORK_BULLETIN_TTL_S seconds a cached bulletin stays fresh (default 900)
"""

from __future__ import annotations

import os
from typing import Optional

DEFAULT_TTL_S = 900.0

# The hub endpoint. Not a default — `configure()` requires the env var to be
# set, because a satellite that silently starts calling a hub it was never
# pointed at is the kind of surprise a template must not ship. This is here so
# `.env.example` and the docs have one place to copy from.
HUB_BULLETIN_URL = "https://2plot.dev/api/network/bulletin"


def url() -> Optional[str]:
    return os.environ.get("NETWORK_BULLETIN_URL") or None


def _ttl() -> float:
    try:
        return max(60.0, float(os.environ.get("NETWORK_BULLETIN_TTL_S",
                                              DEFAULT_TTL_S)))
    except (TypeError, ValueError):
        return DEFAULT_TTL_S


def app_id() -> str:
    """This app's key in the hub's network directory.

    Reused from ``lib.satellite_reporter`` rather than hard-coded, so a fork
    that sets ``SATELLITE_APP_KEY`` for its traffic rollups is automatically
    identified the same way here. A satellite left announcing itself as
    "boilerplate" would receive the template's announcements and the hub's
    "who is rendering the bulletin" view would count it as this repo.
    """
    from lib.satellite_reporter import app_key

    return app_key()


def configure() -> bool:
    """Point the package at the hub's bulletin. Returns whether it did.

    Fail-open by design, in both directions. With no URL the feature is off
    and the viewer header still renders — the package ships default tips and
    an empty-state for announcements, which is what
    `tests/test_llms_routes.py::test_the_banner_renders_its_panels_without_a_bulletin`
    pins. With a URL that is unreachable, the package's client degrades
    silently rather than failing a page render: a hub outage must not take the
    documentation down with it.
    """
    endpoint = url()
    if not endpoint:
        return False

    try:
        from dash_improve_my_llms import configure_bulletin
    except ImportError:  # pragma: no cover - older releases lack the feature
        return False

    configure_bulletin(url=endpoint, ttl=_ttl(), app_id=app_id())
    return True
