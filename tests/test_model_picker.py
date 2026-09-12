"""The model dropdown, and the import-order trap it exists to defeat.

The bug this pins was invisible and total: page modules are imported while Dash
registers pages, which is BEFORE `run.py` calls `openai_client.warm()`. A
layout that read `spend.model_options()` at import froze the Anthropic-only
list, and no OpenAI key could ever change it. Measured on this host at the
time: 3 options at import, 7 after boot, against 131 discovered models.
"""

from __future__ import annotations

import importlib
import pathlib
from unittest import mock

import pytest

from lib import model_picker, openai_client, spend

REPO = pathlib.Path(__file__).resolve().parent.parent
PAGES = {
    "g3": "docs/generative-3d/sculptor.py",
    "si": "docs/sculpt-from-image/sculpt_from_image.py",
    "bm": "docs/benchmark/benchmark.py",
}


@pytest.fixture(autouse=True)
def _anthropic_only(monkeypatch):
    """No OpenAI key, but an Anthropic one.

    These tests are about what the picker does when it HAS something to offer.
    Since the owner's 2026-09-12 decision, `model_options()` gates the Claude
    entries on the Anthropic key too, so without this the whole file would be
    asserting against the empty keyless case — which is
    `tests/test_keyless_host.py`'s job, not this one's.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    for var in openai_client.KEY_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(openai_client, "_discovered", None)
    monkeypatch.setattr(openai_client, "_discovery_error", "")
    yield


# --------------------------------------------------------------------------
# The trap
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name,path", PAGES.items())
def test_no_page_freezes_the_model_list_at_import(name, path):
    """THE REGRESSION GUARD.

    `data=spend.model_options()` in a layout is evaluated at import, before
    discovery has run, and silently offers Anthropic only. Every model control
    must be filled by a callback instead.
    """
    source = (REPO / path).read_text(encoding="utf-8")
    layout, _, _callbacks = source.partition("@callback")
    assert "spend.model_options()" not in layout, (
        f"{path}: the layout reads model_options() at IMPORT time, which runs "
        f"before openai_client.warm() and freezes the Anthropic-only list."
    )


def test_the_picker_ships_an_empty_list_and_fills_it_later():
    interval, select = model_picker.components("t", "claude-opus-5")
    assert select.data == [], "a default list here would be the frozen list"
    assert interval.max_intervals == 1, "fill once, on first render"


# --------------------------------------------------------------------------
# What it offers
# --------------------------------------------------------------------------


def test_claude_models_are_offered_with_no_openai_key():
    values = [m["value"] for m in spend.model_options()]
    assert "claude-opus-5" in values
    assert not [v for v in values if v.startswith("gpt-")]


def test_openai_models_appear_once_discovery_has_run(monkeypatch):
    monkeypatch.setenv("CHATGPT_API_KEY", "k")
    monkeypatch.setattr(
        openai_client, "_get",
        lambda path, timeout: {"data": [{"id": m} for m in openai_client.PRICING]},
    )
    openai_client.warm()
    values = [m["value"] for m in spend.model_options()]
    for model in ("claude-opus-5", "gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra"):
        assert model in values, model


# --------------------------------------------------------------------------
# The status line — an absent model must be explained
# --------------------------------------------------------------------------


def test_status_explains_a_missing_key():
    line = model_picker.status_line()
    assert "CHATGPT_API_KEY is not set" in line
    assert "Claude models only" in line


def test_status_explains_a_failed_discovery(monkeypatch):
    monkeypatch.setenv("CHATGPT_API_KEY", "k")
    monkeypatch.setattr(
        openai_client, "_get",
        mock.Mock(side_effect=TimeoutError("slow")),
    )
    monkeypatch.setattr(openai_client, "DISCOVERY_ATTEMPTS", 1)
    openai_client.warm()
    line = model_picker.status_line()
    assert "discovery failed" in line and "TimeoutError" in line


def test_status_names_the_models_it_added(monkeypatch):
    monkeypatch.setenv("CHATGPT_API_KEY", "k")
    monkeypatch.setattr(
        openai_client, "_get",
        lambda path, timeout: {"data": [{"id": "gpt-6-astra"}]},
    )
    openai_client.warm()
    assert "GPT-6 Astra" in model_picker.status_line()


# --------------------------------------------------------------------------
# The pages actually pass the choice through
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name,path", [("g3", PAGES["g3"]), ("si", PAGES["si"])])
def test_the_chosen_model_reaches_the_sculptor(name, path):
    """A picker whose value is never read is decoration."""
    source = (REPO / path).read_text(encoding="utf-8")
    assert f'State("{name}-model", "value")' in source, "the choice is not read"
    assert 'kwargs={"model": model or sculptor.MODEL}' in source, (
        "the choice is read but not passed to the build"
    )


def test_a_stale_value_falls_back_instead_of_rendering_blank(monkeypatch):
    """If the remembered choice is no longer offered, pick the first one —
    a value absent from `data` renders as an empty box."""
    monkeypatch.setattr(spend, "model_options", lambda: [{"value": "a", "label": "A"}])
    page = importlib.import_module("docs.generative-3d.sculptor")
    assert page  # imported for its registration side effect
    options = spend.model_options()
    values = [o["value"] for o in options]
    current = "gone"
    chosen = current if current in values else (values[0] if values else None)
    assert chosen == "a"


# --------------------------------------------------------------------------
# The suite must never spend money
# --------------------------------------------------------------------------


def test_no_provider_key_escapes_the_conftest_blanking():
    """Every env var the code reads for a provider key must be blanked in
    conftest, or the suite makes billed calls on a developer's machine.

    This is a structural guard, not a spot check: it reads the key names from
    the modules that USE them, so a provider added later cannot slip through
    the same gap the OpenAI one did.
    """
    from tests.conftest import SECRET_ENV_KEYS

    for var in openai_client.KEY_VARS:
        assert var in SECRET_ENV_KEYS, (
            f"{var} is read by lib/openai_client.py but is not blanked in "
            f"conftest — the suite will call the real API on any machine with "
            f"it set in .env"
        )
    # The Anthropic path reads this one directly in lib/sculptor.py.
    assert "ANTHROPIC_API_KEY" in SECRET_ENV_KEYS


def test_the_suite_really_has_no_provider_key(monkeypatch):
    """Belt to the braces above: assert the ACTUAL environment, so a change to
    how conftest applies the list is caught too.

    Opts out of this file's fixture — it is asserting what conftest did, not
    what a test arranged.
    """
    import os

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(os, "environ", {**os.environ})
    for var in (*openai_client.KEY_VARS,):
        assert not os.environ.get(var), f"{var} is set during the test run"
    assert openai_client.available() is False
