"""A bounded poll, and a clientside guard for the state where the server cannot answer.

WHY THIS EXISTS
---------------
Observed on this host, 2026-09-13: a tab left open on /sculpt-from-image across
a restart posted a callback id the running server did not have, and Dash replied
500 to every tick — at `interval=700`, forever, with a spinner that never
stopped. The owner read it as a hung build.

The cause was benign (the tab predated the commit that widened the poll's output
list, and `create_callback_id` hashes only the INPUTS, so the id's `@hash`
matched while the output list did not). The CONSEQUENCE is not benign, and it is
not a development artefact: a deploy swaps the container, and any tab open
mid-build is in exactly that state. Every release that changes a callback's
outputs invalidates open tabs.

TWO MECHANISMS, DELIBERATELY
----------------------------
1. A CEILING. `max_intervals` bounds the tick count, so a poll cannot run
   forever even if nothing else works — no JavaScript, no store, no server.
2. A STALE GUARD, CLIENTSIDE. The server poll writes the tick it last answered
   on into a store; a clientside callback compares that against the live tick
   count and, after `STALE_TICKS` ticks with no answer, says so and stops the
   timer. It is clientside because it has to run in precisely the state where
   server callbacks cannot.

The ceiling alone would leave ~15 minutes of silent 500s; the guard alone would
not survive a browser that never loads the JS. Neither is redundant.

WHAT THIS CANNOT DO
-------------------
It cannot rescue a tab older than itself. The guard ships IN the layout, so a
tab loaded before this commit has no guard in it — the owner's 500 loop is fixed
by a reload, not by this. What this prevents is the NEXT deploy doing it again.

`alive` MEANS "THE SERVER ANSWERED", NOT "SOMETHING CHANGED"
-----------------------------------------------------------
Every return path of a poll must advance it, including the ones that report no
progress. A store advanced only when a part arrives would trip the guard during
any build whose first model call takes longer than `STALE_TICKS` ticks — which
is most of them.
"""

from __future__ import annotations

import json
import math
from typing import Any, Iterable, List, Sequence, Tuple

from dash import Input, Output, State, clientside_callback, dcc

from lib import build_stream

#: Poll period, shared by every page that drives a build. One value, because a
#: ceiling derived from a different interval than the timer actually uses is a
#: ceiling in name only.
INTERVAL_MS = 700

#: Ticks without a server answer before the page says it is out of date. Five
#: is ~3.5s: long enough to ride out a slow response, short enough that nobody
#: watches a dead spinner.
STALE_TICKS = 5

#: DERIVED, not chosen. A run older than the store's TTL has been pruned, so
#: `take()` can never return anything again and polling past it is provably
#: pointless. If the TTL changes, this follows.
MAX_INTERVALS = math.ceil(build_stream.RUN_TTL_SECONDS * 1000 / INTERVAL_MS)

#: What the page says. Names the remedy, because "reload" is the only thing the
#: reader can actually do about a layout that no longer matches the server.
STALE_MESSAGE = "This page is out of date — reload it to start a new build."

_JS = """
function (tick, alive) {
    var no = window.dash_clientside.no_update;
    var idle = [];
    for (var i = 0; i < %(arity)d; i++) { idle.push(no); }
    if (tick === null || tick === undefined) { return idle; }
    var base = (alive && typeof alive.tick === 'number') ? alive.tick : 0;
    if (tick - base <= %(stale)d) { return idle; }
    return %(values)s;
}
"""


def is_stale(tick: Any, alive: Any, stale_ticks: int = STALE_TICKS) -> bool:
    """The guard's decision, in Python, for tests and for reasoning.

    The shipped guard is the JavaScript below; this is its twin, and
    `tests/test_poll_guard.py` executes both over the same table so the two
    cannot drift.
    """
    if not isinstance(tick, (int, float)) or isinstance(tick, bool):
        return False
    base = alive.get("tick") if isinstance(alive, dict) else None
    if not isinstance(base, (int, float)) or isinstance(base, bool):
        base = 0
    return (tick - base) > stale_ticks


def components(prefix: str) -> List[Any]:
    """The bounded timer and the liveness store, for a page's layout."""
    return [
        dcc.Interval(
            id=f"{prefix}-poll",
            interval=INTERVAL_MS,
            disabled=True,
            max_intervals=MAX_INTERVALS,
        ),
        dcc.Store(id=f"{prefix}-alive"),
    ]


def tick_value(tick: Any) -> dict:
    """What a poll returns for its `-alive` output: the tick it answered on."""
    return {"tick": tick if isinstance(tick, (int, float)) else 0}


def guard_js(arity: int, values: Sequence[Any], stale_ticks: int = STALE_TICKS) -> str:
    """The guard's source, with the stale values baked in.

    Built rather than hand-written so the array it returns cannot fall out of
    step with the output list it is registered against.
    """
    return _JS % {
        "arity": arity,
        "stale": stale_ticks,
        "values": json.dumps(list(values)),
    }


def register(prefix: str, status_id: str,
             resets: Iterable[Tuple[str, str, Any]] = ()) -> None:
    """Wire the stale guard for one page.

    `resets` are the page's own "stop looking busy" outputs — its spinner, its
    button's loading flag — as (component_id, property, value). A message under
    a still-spinning button reads as a slow build, not a stale page, so saying
    so without clearing them would be half a fix.
    """
    outputs = [
        Output(status_id, "children", allow_duplicate=True),
        Output(status_id, "color", allow_duplicate=True),
        Output(status_id, "hide", allow_duplicate=True),
        Output(f"{prefix}-poll", "disabled", allow_duplicate=True),
    ]
    values: List[Any] = [STALE_MESSAGE, "yellow", False, True]
    for component_id, prop, value in resets:
        outputs.append(Output(component_id, prop, allow_duplicate=True))
        values.append(value)

    clientside_callback(
        guard_js(len(outputs), values),
        outputs,
        Input(f"{prefix}-poll", "n_intervals"),
        State(f"{prefix}-alive", "data"),
        prevent_initial_call=True,
    )
