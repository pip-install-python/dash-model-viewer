"""Every page that spends money says what it may cost, and what it did.

/benchmark has done this since it was written — "the cost is shown BEFORE you
press the button, not after" — and the two streaming pages did not, which is
what the owner reported. These tests hold all three to it.
"""

from __future__ import annotations

import importlib
import pathlib

import pytest

from lib import build_stream, spend

REPO = pathlib.Path(__file__).resolve().parent.parent
SPENDING_PAGES = ("g3", "si")


def _page(prefix):
    return importlib.import_module({
        "g3": "docs.generative-3d.sculptor",
        "si": "docs.sculpt-from-image.sculpt_from_image",
    }[prefix])


# --------------------------------------------------------------------------
# Before
# --------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", SPENDING_PAGES)
def test_the_page_prices_the_run_before_the_button(prefix):
    line = _page(prefix).show_estimate("claude-opus-5")
    assert "$" in line and "for this run" in line


@pytest.mark.parametrize("prefix", SPENDING_PAGES)
def test_the_estimate_tracks_the_chosen_model(prefix):
    """Choosing Opus over Haiku is choosing a 5x bill, and the only moment
    that fact is useful is before the click."""
    page = _page(prefix)
    cheap = page.show_estimate("claude-haiku-4-5")
    dear = page.show_estimate("claude-opus-5")
    assert cheap != dear, "the estimate must change with the model"
    assert spend.estimate_usd("claude-haiku-4-5", 4000) < spend.estimate_usd(
        "claude-opus-5", 4000
    )


def test_the_estimate_is_an_upper_bound_not_a_guess():
    """`estimate_usd` prices every call as if it used its whole output budget,
    so the figure reported afterwards should nearly always be lower. A demo
    that under-promises cost is the one that surprises somebody."""
    ceiling = spend.estimate_usd("claude-opus-5", 4000)
    realistic = spend.cost_usd("claude-opus-5", input_tokens=1500, output_tokens=1800)
    assert realistic < ceiling


def test_the_estimate_shows_what_is_left_on_the_host():
    line = spend.estimate_line("claude-opus-5", 4000)
    assert "left on this shared host" in line
    assert "calls" in line


def test_an_unpriced_model_is_flagged_rather_than_priced_at_zero():
    """`PRICING.get(model, (0.0, 0.0))` would otherwise render "~$0.000",
    which reads as free rather than as unknown."""
    line = spend.estimate_line("some-model-nobody-priced", 4000)
    assert "no price table entry" in line


# --------------------------------------------------------------------------
# After
# --------------------------------------------------------------------------


def _finished_run(usd=0.0871, seconds=34.2):
    run = build_stream.new_run()
    build_stream.emit(run, {
        "phase": "done", "total": 2,
        "data_url": "data:model/gltf-binary;base64,ZZZ",
        "manifest": {"name": "Lighthouse", "notes": "a tower"},
        "notes": [], "part_count": 12, "seconds": seconds, "usd": usd,
    })
    build_stream.finish(run, ok=True)
    return run


@pytest.mark.parametrize("prefix", SPENDING_PAGES)
def test_the_page_reports_what_the_run_ACTUALLY_cost(prefix):
    page = _page(prefix)
    run = _finished_run()
    note = page.poll(1, run, "x")[2] if prefix == "g3" else page.poll(1, run)[2]
    assert "$0.0871" in note, f"the actual cost is missing from: {note}"
    assert "34s" in note


def test_the_actual_cost_comes_from_measured_usage_not_the_estimate():
    """The done event carries `usd` recorded from the provider's own reported
    token counts. Rendering the estimate again would be a plausible number
    that is never corrected by reality."""
    assert "0.0100" in spend.actual_line(0.01)
    assert spend.actual_line(0.01) != spend.estimate_line("claude-opus-5", 4000)


def test_four_decimals_because_a_sculpt_costs_cents():
    """Two decimals renders most real sculpts as "$0.00", which reads as free."""
    assert "$0.0009" in spend.actual_line(0.0009)
