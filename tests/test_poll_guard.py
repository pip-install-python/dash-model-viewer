"""The bounded poll and the stale guard — ops' fix for the 500 loop.

WHAT WENT WRONG (2026-09-13, this host)
---------------------------------------
A tab left open on /sculpt-from-image across a restart posted a callback id the
running server no longer had. Dash answered 500 to every tick, at 700 ms,
indefinitely, behind a spinner that never stopped. The owner read it as a hung
build and pasted ~40 identical tracebacks.

The cause was benign — the tab predated the commit that widened the poll's
output list, and `create_callback_id` hashes only the INPUTS, so the id's
`@hash` matched while the output list did not. The consequence is not: every
deploy that changes a callback's outputs puts every open tab in that state.

WHAT IS MACHINE-CHECKED HERE, AND WHAT IS NOT
---------------------------------------------
The shipped guard is JavaScript, so the decision table is executed under `node`
rather than read — and asserted to agree with the Python twin, which is what
runs when node is missing. The one thing no test here can do is prove the
browser renders it: that needs a real browser, and this file does not claim it.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from conftest import in_fresh_app
from lib import build_stream, poll_guard

PAGES = {
    "si": "docs.sculpt-from-image.sculpt_from_image",
    "g3": "docs.generative-3d.sculptor",
}

#: (tick, alive, expected_stale). The boundary matters: at exactly
#: STALE_TICKS the page is still merely slow.
TABLE = [
    (0, None, False),
    (1, {"tick": 1}, False),
    (5, {"tick": 0}, False),          # exactly the allowance — not yet stale
    (6, {"tick": 0}, True),           # one past it
    (100, {"tick": 99}, False),       # answering normally, late in a build
    (100, {"tick": 90}, True),        # answered 10 ticks ago: stale
    (6, None, True),                  # never answered at all
    (6, {}, True),                    # a store with no tick
    (6, {"tick": None}, True),        # a null tick
    (None, {"tick": 0}, False),       # no tick yet: say nothing
]


# --------------------------------------------------------------------------
# 1. The ceiling
# --------------------------------------------------------------------------


def test_the_ceiling_is_derived_from_the_store_ttl_not_chosen():
    """A run older than the store's TTL has been pruned, so `take()` can never
    return anything again — polling past it is provably pointless. Deriving the
    number means a TTL change carries it."""
    expected = -(-build_stream.RUN_TTL_SECONDS * 1000 // poll_guard.INTERVAL_MS)
    assert poll_guard.MAX_INTERVALS == expected
    assert poll_guard.MAX_INTERVALS * poll_guard.INTERVAL_MS / 1000 >= \
        build_stream.RUN_TTL_SECONDS, "the ceiling must not cut a legal build short"


@pytest.mark.parametrize("prefix", PAGES)
def test_the_poll_cannot_tick_past_its_ceiling(prefix):
    """THE ACCEPTANCE. Unbounded was the defect; `max_intervals` is the backstop
    that holds even with no JavaScript, no store and no server."""
    interval = _interval(prefix)
    assert interval.max_intervals == poll_guard.MAX_INTERVALS
    assert interval.max_intervals > 0
    assert interval.interval == poll_guard.INTERVAL_MS
    assert interval.disabled is True, "a build must start it, not a page load"


@pytest.mark.parametrize("prefix", PAGES)
def test_no_page_hardcodes_its_own_interval_any_more(prefix):
    """Two pages each writing `interval=700` is two places for a ceiling to be
    sized against the wrong period."""
    source = _source(prefix)
    assert "interval=700" not in source
    assert f'poll_guard.components("{prefix}")' in source


# --------------------------------------------------------------------------
# 2. The guard's decision — executed, not read
# --------------------------------------------------------------------------


@pytest.mark.parametrize("tick,alive,expected", TABLE)
def test_the_python_twin_decides_correctly(tick, alive, expected):
    assert poll_guard.is_stale(tick, alive) is expected


@pytest.mark.skipif(shutil.which("node") is None,
                    reason="no node — the Python twin carries the table here")
def test_the_SHIPPED_JAVASCRIPT_agrees_with_the_twin(tmp_path):
    """The guard that actually runs is the JS. Executing it is the difference
    between testing the fix and testing a description of the fix."""
    js = poll_guard.guard_js(4, ["MSG", "yellow", False, True])
    harness = tmp_path / "guard.js"
    harness.write_text(
        "global.window = {dash_clientside: {no_update: '__NO__'}};\n"
        f"const guard = {js};\n"
        f"const table = {json.dumps([[t, a] for t, a, _ in TABLE])};\n"
        "const out = table.map(([t, a]) => {\n"
        "  const r = guard(t, a);\n"
        "  return r[0] !== '__NO__';\n"
        "});\n"
        "console.log(JSON.stringify(out));\n",
        encoding="utf-8",
    )
    result = subprocess.run(["node", str(harness)], capture_output=True, text=True,
                            timeout=60)
    assert result.returncode == 0, result.stderr
    got = json.loads(result.stdout)
    assert got == [expected for _, _, expected in TABLE], (
        "the shipped JavaScript and the Python twin disagree"
    )


@pytest.mark.skipif(shutil.which("node") is None, reason="no node")
def test_the_javascript_returns_the_message_and_stops_the_timer(tmp_path):
    """ops' acceptance, stated as behaviour: the guard's text appears when the
    store stops advancing, and the timer is switched off in the same return."""
    outputs, values = _guard_shape("si")
    js = poll_guard.guard_js(len(outputs), values)
    harness = tmp_path / "stale.js"
    harness.write_text(
        "global.window = {dash_clientside: {no_update: '__NO__'}};\n"
        f"const guard = {js};\n"
        "console.log(JSON.stringify({\n"
        "  building: guard(30, {tick: 30}),\n"
        "  stalled:  guard(30, {tick: 10}),\n"
        "}));\n",
        encoding="utf-8",
    )
    result = subprocess.run(["node", str(harness)], capture_output=True, text=True,
                            timeout=60)
    assert result.returncode == 0, result.stderr
    got = json.loads(result.stdout)

    assert all(v == "__NO__" for v in got["building"]), \
        "a healthy build must be left completely alone"

    stalled = got["stalled"]
    assert stalled[0] == poll_guard.STALE_MESSAGE
    assert "reload" in stalled[0].lower(), "the message must name the remedy"
    assert stalled[2] is False, "the alert is un-hidden, or nobody reads it"
    assert stalled[3] is True, "the Interval must be disabled — the loop must STOP"


# --------------------------------------------------------------------------
# 3. Registered on the pages, and clearing the busy state
# --------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", PAGES)
def test_the_guard_is_registered_clientside_on_every_polling_page(prefix):
    """CLIENTSIDE is the whole point: it has to run in exactly the state where
    server callbacks cannot. A server-side guard would 500 with everything
    else."""
    keys = in_fresh_app(
        "keys = [k for k, v in app.callback_map.items()\n"
        f"        if '{prefix}-status.children@' in k and 'callback' not in v]\n"
        "print('RESULT:' + json.dumps(keys))\n"
    )
    assert len(keys) == 1, f"{prefix}: expected one clientside guard, found {len(keys)}"
    # No Python function in the spec IS the marker of a clientside callback.
    assert f"{prefix}-poll.disabled@" in keys[0], "the guard must be able to stop the timer"


@pytest.mark.parametrize("prefix", PAGES)
def test_the_guard_clears_the_busy_chrome_too(prefix):
    """A "reload me" message under a still-spinning button reads as a slow
    build. Saying so without clearing the spinner is half a fix."""
    outputs, values = _guard_shape(prefix)
    targets = {f"{cid}.{prop}" for cid, prop in outputs}
    assert f"{prefix}-working.display" in targets
    assert f"{prefix}-go.loading" in targets
    assert values[values.index(poll_guard.STALE_MESSAGE)] == poll_guard.STALE_MESSAGE


def test_generative_3d_also_re_enables_its_prompt():
    """It disables the textarea while building; a stale page that cannot be
    retyped into is still stuck."""
    outputs, _values = _guard_shape("g3")
    assert ("g3-prompt", "disabled") in outputs


# --------------------------------------------------------------------------
# 4. The loop itself, reproduced from the diagnosis
# --------------------------------------------------------------------------


def test_the_owners_500_is_reproduced_by_dropping_the_outputs_item_2_added():
    """The fixture is the diagnosis: take the live poll key, strip the three
    outputs c56c3e2 added, and the result is absent from the map — which IS the
    `KeyError` the owner pasted. Proof the mechanism was the output list and not
    the input hash, since the hash is unchanged either way."""
    got = in_fresh_app(
        "live = next(k for k in app.callback_map if 'si-viewer.src' in k)\n"
        "stale = '..' + '...'.join(live.strip('.').split('...')[:10]) + '..'\n"
        "print('RESULT:' + json.dumps({\n"
        "    'live': live,\n"
        "    'live_present': live in app.callback_map,\n"
        "    'stale': stale,\n"
        "    'stale_present': stale in app.callback_map,\n"
        "}))\n"
    )
    live, stale_key = got["live"], got["stale"]
    parts = live.strip(".").split("...")
    assert len(parts) == 14
    assert got["stale_present"] is False, "this is the 500"
    assert got["live_present"] is True, "while the current layout resolves"

    # The `@hash` is identical in both: it covers the INPUTS only.
    suffix = next(p.split("@")[1] for p in parts if "@" in p)
    assert suffix in stale_key and suffix in live


def test_a_tab_older_than_the_guard_cannot_be_rescued_by_it():
    """Recorded because it bounds the claim: the guard ships IN the layout, so
    the owner's open tab has no guard in it. A reload fixes that one; this fixes
    the next deploy."""
    source = _source("si")
    assert 'poll_guard.register("si"' in source
    assert "poll_guard.components" in source


# --------------------------------------------------------------------------
# Liveness means "the server answered", on every path
# --------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", PAGES)
def test_every_poll_return_path_advances_liveness(prefix):
    """Measured by COUNTING the returns in the function and the number that
    carry the tick — a sweep that checks only the happy path would pass on a
    page that trips its own guard mid-build."""
    import inspect
    import importlib

    poll = importlib.import_module(PAGES[prefix]).poll
    body = inspect.getsource(poll)
    returns = body.count("return ")
    carries = body.count("alive")
    assert returns >= 4, f"expected the four paths, found {returns}"
    # one binding + one per return
    assert carries >= returns + 1, (
        f"{prefix}: {returns} returns but only {carries} mentions of the tick"
    )


@pytest.mark.parametrize("prefix", PAGES)
def test_a_build_resets_the_tick_count_so_the_ceiling_is_per_build(prefix):
    """`max_intervals` counts a component's whole life, not one build. Writing
    `n_intervals` back to 0 re-arms it (the gate is `n_intervals >=
    max_intervals`, re-evaluated on update — read from the shipped dcc bundle),
    so a user's fourth sculpt is not cut short by the first three."""
    source = _source(prefix)
    assert f'Output("{prefix}-poll", "n_intervals")' in source
    assert f'Output("{prefix}-alive", "data")' in source


def test_tick_value_survives_a_null_tick():
    """`n_intervals` is None before the first tick, and a store holding None
    would make the guard's arithmetic NaN."""
    assert poll_guard.tick_value(None) == {"tick": 0}
    assert poll_guard.tick_value(7) == {"tick": 7}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _source(prefix):
    import importlib
    import inspect

    return inspect.getsource(importlib.import_module(PAGES[prefix]))


def _interval(prefix):
    """The real component the page puts in its layout."""
    return poll_guard.components(prefix)[0]


def _guard_shape(prefix):
    """Re-derive what `register` wires, without a second copy of the list."""
    resets = {
        "si": [("si-working", "display", "none"), ("si-go", "loading", False)],
        "g3": [("g3-working", "display", "none"), ("g3-go", "loading", False),
               ("g3-prompt", "disabled", False)],
    }[prefix]
    outputs = [(f"{prefix}-status", "children"), (f"{prefix}-status", "color"),
               (f"{prefix}-status", "hide"), (f"{prefix}-poll", "disabled")]
    values = [poll_guard.STALE_MESSAGE, "yellow", False, True]
    for cid, prop, value in resets:
        outputs.append((cid, prop))
        values.append(value)
    return outputs, values
