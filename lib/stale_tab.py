"""A clientside guard for a tab whose callback graph no longer matches the server.

WHY THIS EXISTS
---------------
Three times on this host the site looked broken while the code was fine — a
switch that did nothing, downloads that did nothing. Each time the cause was the
same: Dash fetches `_dash-dependencies` ONCE, when a tab first loads, but page
layouts come fresh from the server on every in-app navigation. After a restart
or a deploy the tab renders new controls from a fresh layout and wires them to a
map that has never heard of them. Nothing errors; the control silently does
nothing, and with `debug` off there is no hot reload to tell the tab.

THE MECHANISM (ops' ruling, SYNC-1.6.46 item 12's third half)
-------------------------------------------------------------
Record a fingerprint in TAB MEMORY on first load; on every later in-app
navigation, take it again and compare. Different means stale, and the page says
the same sentence as the poll guard.

- PRIMARY signal: `/healthz`'s `build` key (~300 B). A changed build IS a
  deploy, and in production the graph cannot change within a build, so build
  equality is graph equality there.
- FALLBACK when `build` is null or absent (every local run — the key comes from
  `RENDER_GIT_COMMIT`): a fingerprint of the served `_dash-dependencies`, made
  order-independent by sorting canonical entries, so a restart that changes
  nothing compares equal.

WHY NOT "BAKED AT REGISTRATION" (the spec this replaced)
--------------------------------------------------------
Measured on this host: 2 callbacks exist when the app shell registers, 61 in the
final served graph. A fingerprint baked then would differ from the server on
every load — a permanent false alarm. Registering last does not help either: the
guard would be inside the graph it hashes. And a check at load ALONE is inert,
because at load everything is fresh by definition; staleness only becomes
visible on a later check. Hence one small GET per in-app navigation.

WHAT THIS CANNOT DO
-------------------
It cannot rescue a tab older than itself — the guard ships in the page. What it
prevents is the NEXT deploy doing it silently. And it fails QUIET, never loud: a
probe that errors, times out, or answers without the key it was recorded with
(a mid-swap `/healthz` can read empty) says nothing, and the next navigation
asks again. A false "reload" is worse than no guard.

Neither probe path is recorded by the analytics tracker (`/healthz` and
`/_dash-dependencies` are both in its skip list), so this changes nothing about
what the site collects.
"""

from __future__ import annotations

from typing import Any, Optional

import dash_mantine_components as dmc
from dash import Input, Output, State, clientside_callback, dcc

#: The poll guard's sentence, without its page-specific tail. One sentence for
#: one condition, wherever the page notices it.
STALE_MESSAGE = "This page is out of date — reload it."

BASELINE_ID = "stale-tab-baseline"
ALERT_ID = "stale-tab-alert"

#: A probe slower than this is treated as no answer, not as a verdict.
PROBE_TIMEOUT_MS = 5000

#: The shipped guard. The probe and the fingerprint are defined inside the
#: function so the whole thing is one self-contained value `node` can execute.
_JS = r"""
async function (pathname, baseline) {
    var no = window.dash_clientside.no_update;
    var idle = [no, no, no, no];
    if (pathname === null || pathname === undefined) { return idle; }
    if (baseline && baseline.stale) { return idle; }   // said once; stop asking

    function cyrb53(str) {
        var h1 = 0xdeadbeef, h2 = 0x41c6ce57;
        for (var i = 0; i < str.length; i++) {
            var ch = str.charCodeAt(i);
            h1 = Math.imul(h1 ^ ch, 2654435761);
            h2 = Math.imul(h2 ^ ch, 1597334677);
        }
        h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
        h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
        return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(16);
    }
    function canon(v) {
        if (Array.isArray(v)) { return '[' + v.map(canon).join(',') + ']'; }
        if (v && typeof v === 'object') {
            return '{' + Object.keys(v).sort().map(function (k) {
                return JSON.stringify(k) + ':' + canon(v[k]);
            }).join(',') + '}';
        }
        return JSON.stringify(v === undefined ? null : v);
    }
    function fingerprint(deps) {
        var rows = deps.map(canon).sort();
        return rows.length + ':' + cyrb53(rows.join('\n'));
    }
    async function get(url) {
        var ctl = (typeof AbortController === 'function') ? new AbortController() : null;
        var timer = ctl ? setTimeout(function () { ctl.abort(); }, %(timeout)d) : null;
        try {
            var r = await fetch(url, {cache: 'no-store', credentials: 'same-origin',
                                      signal: ctl ? ctl.signal : undefined});
            if (!r.ok) { return null; }
            return await r.json();
        } catch (e) {
            return null;
        } finally {
            if (timer) { clearTimeout(timer); }
        }
    }
    function prefix() {
        try {
            var cfg = JSON.parse(document.getElementById('_dash-config').textContent);
            return cfg.requests_pathname_prefix || '/';
        } catch (e) {
            return '/';
        }
    }
    async function probe(kind) {
        if (kind === 'build') {
            var h = await get('/healthz');
            return (h && typeof h.build === 'string' && h.build) ? h.build : null;
        }
        var deps = await get(prefix() + '_dash-dependencies');
        return Array.isArray(deps) ? fingerprint(deps) : null;
    }

    if (!baseline || !baseline.kind) {
        // First load: RECORD, never judge. Prefer the build; fall back to the graph.
        var build = await probe('build');
        if (build) { return [{kind: 'build', value: build}, no, no, no]; }
        var graph = await probe('graph');
        if (graph) { return [{kind: 'graph', value: graph}, no, no, no]; }
        return idle;   // could not record; the next navigation tries again
    }

    var now = await probe(baseline.kind);
    if (now === null || now === baseline.value) { return idle; }
    return [
        {kind: baseline.kind, value: baseline.value, stale: true, seen: now},
        %(message)s, false, 'yellow'
    ];
}
"""


def verdict(baseline: Any, observed: Optional[str]) -> str:
    """The guard's decision, in Python: `record`, `stale`, or `quiet`.

    The shipped guard is the JavaScript; `tests/test_stale_tab.py` executes it
    under node against a mocked server and asserts this twin agrees.
    """
    if not isinstance(baseline, dict) or not baseline.get("kind"):
        return "record" if observed else "quiet"
    if baseline.get("stale"):
        return "quiet"
    if observed is None or observed == baseline.get("value"):
        return "quiet"
    return "stale"


def guard_js() -> str:
    import json

    return _JS % {"timeout": PROBE_TIMEOUT_MS, "message": json.dumps(STALE_MESSAGE)}


def baseline_store() -> Any:
    """The tab-memory baseline.

    storage_type="memory": dies with the tab, survives in-app navigation —
    exactly the lifetime of the callback map it stands in for.
    """
    return dcc.Store(id=BASELINE_ID, storage_type="memory")


def alert() -> Any:
    """Hidden until the guard fires; the guard writes its text."""
    return dmc.Alert(id=ALERT_ID, hide=True, color="yellow",
                     title="Out of date", mb="md")


def register(location_id: str = "url") -> None:
    """Wire the guard to the shell's Location: one probe per navigation."""
    clientside_callback(
        guard_js(),
        Output(BASELINE_ID, "data"),
        Output(ALERT_ID, "children"),
        Output(ALERT_ID, "hide"),
        Output(ALERT_ID, "color"),
        Input(location_id, "pathname"),
        State(BASELINE_ID, "data"),
    )
