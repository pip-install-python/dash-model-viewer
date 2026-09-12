"""The production state: no provider keys, and every page saying so.

The owner's decision of 2026-09-12 is that no Render service carries a
provider key — the sites are documentation and do no production spend. So
"no keys" is the NORMAL deployed state, not a misconfiguration, and these
tests hold the pages to reading as deliberately off rather than as broken.

conftest blanks the keys for the whole suite, so this is the default here.
"""

from __future__ import annotations

import importlib
import pathlib

import pytest

from lib import model_picker, openai_client, spend

REPO = pathlib.Path(__file__).resolve().parent.parent
PAGE_MD = {
    "generative-3d": "docs/generative-3d/generative-3d.md",
    "sculpt-from-image": "docs/sculpt-from-image/sculpt-from-image.md",
    "benchmark": "docs/benchmark/benchmark.md",
}


def test_the_suite_is_running_the_keyless_case():
    """Guard the guard: every assertion below is vacuous with a key set."""
    assert spend.anthropic_available() is False
    assert openai_client.available() is False
    assert spend.any_provider_available() is False


# --------------------------------------------------------------------------
# The picker
# --------------------------------------------------------------------------


def test_the_picker_is_empty_rather_than_offering_models_that_cannot_run():
    """It used to list three Claude models unconditionally. A dropdown full of
    options that all fail is worse than an empty one with a reason."""
    assert spend.model_options() == []


def test_the_status_line_says_the_site_has_no_keys():
    line = model_picker.status_line()
    assert line == spend.NO_KEYS_MESSAGE
    assert "run it locally" in line.lower()


def test_the_status_line_does_not_name_only_one_missing_key():
    """The old line read "Claude models only — CHATGPT_API_KEY is not set",
    which on a host with NEITHER key named the missing one and implied the
    other worked."""
    line = model_picker.status_line()
    assert "Claude models only" not in line


def test_no_price_is_quoted_on_a_host_that_cannot_spend():
    """A number implies the button works."""
    line = spend.estimate_line("claude-opus-5", 4000)
    assert "$" not in line.split("—")[0] or line == spend.NO_KEYS_MESSAGE
    assert line == spend.NO_KEYS_MESSAGE


# --------------------------------------------------------------------------
# The controls
# --------------------------------------------------------------------------


def test_the_benchmark_run_button_is_disabled():
    """This page spends up to four times per click, so an enabled button on a
    keyless host is the worst of the three."""
    bm = importlib.import_module("docs.benchmark.benchmark")
    boxes, options, _status, disabled = bm._fill_models(1)
    assert disabled is True
    assert boxes == [] and options == []


@pytest.mark.parametrize(
    "prefix,button,path",
    [
        ("g3", "g3-go", "docs/generative-3d/sculptor.py"),
        ("si", "si-go", "docs/sculpt-from-image/sculpt_from_image.py"),
    ],
)
def test_the_spending_buttons_are_handed_to_the_picker(prefix, button, path):
    """The page must pass its spending control to `model_picker.register`, or
    nothing ever disables it on a keyless host.

    Asserted against the SOURCE, not `dash._callback.GLOBAL_CALLBACK_LIST`.
    That list is drained into `app.callback_map` when Dash sets the app up,
    which any earlier test using the `client` fixture does — so a registry
    assertion passes alone and fails in the full suite, which is exactly what
    the first version of this test did.
    """
    source = (REPO / path).read_text(encoding="utf-8")
    assert f'model_picker.register("{prefix}", action_ids=["{button}"])' in source, (
        f"{path} does not hand {button} to the picker, so a keyless host would "
        f"show an enabled button that always fails"
    )


def test_the_picker_disables_what_it_is_given():
    """And the mechanism itself: with no provider, the fill returns True for
    the model select and for every action id handed to it."""
    import dash

    before = len(dash._callback.GLOBAL_CALLBACK_LIST)
    model_picker.register("zz", action_ids=["zz-go", "zz-go2"])
    added = dash._callback.GLOBAL_CALLBACK_LIST[before:]
    assert added, "register() must add a callback"
    outputs = str(added[-1]["output"])
    for expected in ("zz-model.disabled", "zz-go.disabled", "zz-go2.disabled"):
        assert expected in outputs, f"{expected} missing from {outputs}"


# --------------------------------------------------------------------------
# It must be written down, or it gets filed as a bug
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name,path", PAGE_MD.items())
def test_each_generative_page_documents_the_keyless_state(name, path):
    prose = " ".join(
        (REPO / path).read_text(encoding="utf-8").replace("*", "").split()
    ).lower()
    assert "runs without provider keys" in prose, f"{path} does not say so"
    assert "expected state, not a fault" in prose, (
        f"{path} does not tell the reader this is not a bug"
    )
    assert ".env" in prose, f"{path} does not say how to run it locally"


def test_the_changelog_records_the_decision():
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8").lower()
    assert "carries no" in text and "chatgpt_api_key" in text
    assert "2026-09-12" in text


def test_the_no_keys_message_is_defined_once():
    """Three pages, one sentence — so they cannot drift into three different
    explanations of the same state."""
    for path in PAGE_MD.values():
        assert (REPO / path).exists()
    assert spend.NO_KEYS_MESSAGE
    assert model_picker.status_line() is spend.NO_KEYS_MESSAGE or (
        model_picker.status_line() == spend.NO_KEYS_MESSAGE
    )
