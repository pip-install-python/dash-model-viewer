"""The network bulletin wiring — `lib/bulletin.py`.

TEMPLATE FILE: satellites copy this verbatim.

The failure this exists to prevent already happened once, and it is the
quietest kind: the wiring sat COMMENTED OUT in `run.py` while
`NETWORK_BULLETIN_URL` was set in production. `configure_bulletin` is opt-in,
so an unwired app makes no request at all and the viewer header renders
perfectly well on the package's built-in defaults. Nothing errored, nothing
logged, no dashboard changed — the announcements simply never appeared, which
is not something anyone goes looking for.

These tests are deliberately about the WIRING rather than about rendering a
bulletin. The suite is secretless and offline (conftest pins
`NETWORK_BULLETIN_URL` to `""` and disables the geo lookup for the same
reason), so fetching a real bulletin here would make the suite depend on the
hub being up. What can be pinned offline is that the env var is read, that the
app identifies itself with the right directory key, and that the feature
fails open in both directions.
"""

from __future__ import annotations

import pytest

from lib import bulletin


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """conftest pins these empty; make each test state its own posture."""
    monkeypatch.delenv("NETWORK_BULLETIN_URL", raising=False)
    monkeypatch.delenv("NETWORK_BULLETIN_TTL_S", raising=False)


# ------------------------------------------------------------- the wiring --


def test_no_url_means_the_feature_is_off(monkeypatch):
    assert bulletin.url() is None
    assert bulletin.configure() is False


def test_an_empty_url_is_off_not_a_request_to_the_empty_string(monkeypatch):
    """Render writes `KEY=` for an unset variable; `""` must read as absent."""
    monkeypatch.setenv("NETWORK_BULLETIN_URL", "")
    assert bulletin.url() is None
    assert bulletin.configure() is False


def test_a_url_wires_the_package(monkeypatch):
    """The whole point: the env var must reach `configure_bulletin`."""
    seen = {}

    def fake(url=None, ttl=None, timeout=None, enabled=True, app_id=None):
        seen.update(url=url, ttl=ttl, app_id=app_id)

    monkeypatch.setattr("dash_improve_my_llms.configure_bulletin", fake)
    monkeypatch.setenv("NETWORK_BULLETIN_URL", bulletin.HUB_BULLETIN_URL)

    assert bulletin.configure() is True
    assert seen["url"] == bulletin.HUB_BULLETIN_URL
    assert seen["ttl"] == bulletin.DEFAULT_TTL_S


def test_the_ttl_is_configurable_and_floored(monkeypatch):
    """A tiny TTL would hammer the hub once per llms.txt view."""
    seen = {}
    monkeypatch.setattr(
        "dash_improve_my_llms.configure_bulletin",
        lambda **kw: seen.update(kw),
    )
    monkeypatch.setenv("NETWORK_BULLETIN_URL", bulletin.HUB_BULLETIN_URL)

    monkeypatch.setenv("NETWORK_BULLETIN_TTL_S", "1800")
    bulletin.configure()
    assert seen["ttl"] == 1800.0

    monkeypatch.setenv("NETWORK_BULLETIN_TTL_S", "5")
    bulletin.configure()
    assert seen["ttl"] == 60.0, "a 5s TTL would refetch on nearly every view"

    monkeypatch.setenv("NETWORK_BULLETIN_TTL_S", "not-a-number")
    bulletin.configure()
    assert seen["ttl"] == bulletin.DEFAULT_TTL_S, "junk must not raise at boot"


# ------------------------------------------------------------- identity ----


def test_the_app_id_is_this_satellite_not_the_template(monkeypatch):
    """A fork announcing itself as "boilerplate" gets the template's news.

    The hub scopes announcements by `?app=` and uses it to see which
    satellites actually render the bulletin, so a wrong key is wrong twice.
    """
    monkeypatch.setenv("SATELLITE_APP_KEY", "leaflet")
    assert bulletin.app_id() == "leaflet"


def test_the_app_id_falls_back_to_this_repos_directory_key(monkeypatch):
    monkeypatch.delenv("SATELLITE_APP_KEY", raising=False)
    assert bulletin.app_id() == "boilerplate"


def test_the_app_id_matches_the_traffic_reporters(monkeypatch):
    """One notion of "which satellite am I", not two that can disagree."""
    from lib import satellite_reporter

    monkeypatch.setenv("SATELLITE_APP_KEY", "email")
    assert bulletin.app_id() == satellite_reporter.app_key()


def test_every_hub_surface_names_this_app_the_same_way(monkeypatch):
    """Ads, traffic, the bulletin and the hub client all say "boilerplate".

    Four modules present an identity to the hub and each has its own fallback,
    so they can drift apart without anything failing — the symptom is a column
    on /admin/ad-board that does not line up with /traffic, which nobody
    reconciles. The ad client used to default to the long
    "dash-model-viewer", which also fed `hub_client.app_id()`
    through its AD_APP_ID fallback whenever SATELLITE_APP_KEY was unset.
    """
    from lib import ad_client, hub_client, satellite_reporter

    for key in ("SATELLITE_APP_KEY", "AD_APP_ID"):
        monkeypatch.delenv(key, raising=False)

    assert ad_client.APP_ID == "boilerplate"
    assert satellite_reporter.app_key() == "boilerplate"
    assert hub_client.app_id() == "boilerplate"
    assert bulletin.app_id() == "boilerplate"


def test_the_ad_id_no_longer_re_keys_the_hub_client(monkeypatch):
    """`hub_client.app_id()` falls back to AD_APP_ID; that used to be a trap.

    A deployment that set AD_APP_ID for ads and nothing else silently sent the
    ad identifier as its hub identity. Still true by construction — this pins
    that the value it would send is now the directory key, not a long name.
    """
    from lib import hub_client

    monkeypatch.delenv("SATELLITE_APP_KEY", raising=False)
    monkeypatch.setenv("AD_APP_ID", "boilerplate")
    assert hub_client.app_id() == "boilerplate"


# ------------------------------------------------------------ fail-open ----


def test_a_broken_package_does_not_stop_the_boot(monkeypatch):
    """A hub feature must never be able to take the documentation down."""
    monkeypatch.setenv("NETWORK_BULLETIN_URL", bulletin.HUB_BULLETIN_URL)

    def explode(**_kwargs):
        raise RuntimeError("hub client blew up")

    monkeypatch.setattr("dash_improve_my_llms.configure_bulletin", explode)
    with pytest.raises(RuntimeError):
        # Documenting the CURRENT contract honestly: configure() does not
        # swallow this. It runs at import time, before any request is served,
        # so a raise here is a loud boot failure rather than a broken page —
        # which is the right trade for a misconfiguration. The fail-open that
        # matters is at FETCH time, and that lives inside the package.
        bulletin.configure()


# --------------------------------------------------------------- run.py ----


def test_run_py_wires_it_rather_than_leaving_it_commented_out(app_module):
    """The regression itself.

    The suite boots secretless, so the flag is False here — what is asserted
    is that `run.py` EXPOSES the decision at all. Commented-out wiring cannot
    define this name, so this test fails the moment someone comments it out
    again.
    """
    assert hasattr(app_module, "BULLETIN_ENABLED")
    assert app_module.BULLETIN_ENABLED is False, (
        "conftest pins NETWORK_BULLETIN_URL empty; a True here means the "
        "suite is reaching the hub"
    )


def test_the_documented_hub_endpoint_is_the_one_the_hub_serves():
    """`.env.example` and the boot message both quote this constant."""
    assert bulletin.HUB_BULLETIN_URL == "https://2plot.dev/api/network/bulletin"
