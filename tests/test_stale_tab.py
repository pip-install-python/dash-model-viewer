"""The stale-tab guard — a tab whose callback map predates the server's.

ops' acceptance (SYNC-1.6.46 item 12's third half), one test each:
- the shape that started this — a tab holding a graph one State short after a
  build change — shows the sentence on the next navigation;
- a navigation with no deploy shows nothing;
- the fallback path, tested with build=null;
- one small GET per in-app navigation, none on load beyond the record.

WHAT IS MACHINE-CHECKED HERE, AND WHAT IS NOT
---------------------------------------------
The guard that ships is JavaScript, so it is EXECUTED under `node` against a
mocked `fetch` — the number of requests it makes is counted, not read off the
source. The fallback's fixtures are the dependency graph a freshly booted app
actually serves, not hand-written lists. No test here proves a browser renders
the alert; that needs a real browser, and this file does not claim it.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess

import pytest

from conftest import BROWSER_UA, in_fresh_app
from lib import poll_guard, stale_tab

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="no node")

#: The BROWSER lane, named: the guard runs in a tab, and a bare test client
#: would be read as a crawler (notes 70/74).
_SERVED = (
    "client = app.server.test_client()\n"
    f"r = client.get('/_dash-dependencies', headers={{'User-Agent': {BROWSER_UA!r}}})\n"
    "assert r.status_code == 200, r.status_code\n"
    "print('RESULT:' + json.dumps(r.get_json()))\n"
)


@pytest.fixture(scope="module")
def served_deps():
    """What a real worker serves at `_dash-dependencies`, from a fresh boot."""
    deps = in_fresh_app(_SERVED)
    assert len(deps) > 50, f"only {len(deps)} callbacks — the app did not boot whole"
    return deps


def _run(tmp_path, steps):
    """Drive the shipped guard through `steps` against a mocked server.

    Each step is {"healthz": <body|None|"fail">, "deps": <list|None|"fail">,
    "pathname": str}; the baseline store is threaded between steps exactly as
    Dash would. Returns, per step, the four outputs and the URLs fetched.
    """
    harness = tmp_path / "stale_tab.js"
    harness.write_text(
        "global.window = {dash_clientside: {no_update: '__NO__'}};\n"
        "global.document = {getElementById: () => "
        "({textContent: JSON.stringify({requests_pathname_prefix: '/'})})};\n"
        f"const guard = {stale_tab.guard_js()};\n"
        f"const steps = {json.dumps(steps)};\n"
        "let current = null, log = [];\n"
        "global.fetch = async (url) => {\n"
        "  log.push(url);\n"
        "  const body = url === '/healthz' ? current.healthz : current.deps;\n"
        "  if (body === 'fail') throw new Error('network');\n"
        "  return {ok: body !== null, json: async () => body};\n"
        "};\n"
        "(async () => {\n"
        "  let baseline = null; const out = [];\n"
        "  for (const s of steps) {\n"
        "    current = s; log = [];\n"
        "    const r = await guard(s.pathname, baseline);\n"
        "    if (r[0] !== '__NO__') baseline = r[0];\n"
        "    out.push({r, fetched: log, baseline});\n"
        "  }\n"
        "  console.log(JSON.stringify(out));\n"
        "})();\n",
        encoding="utf-8",
    )
    result = subprocess.run(["node", str(harness)], capture_output=True,
                            text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _shown(step):
    return step["r"][1] == stale_tab.STALE_MESSAGE and step["r"][2] is False


def _silent(step):
    return step["r"][1:] == ["__NO__"] * 3


def _one_state_short(deps):
    """The graph that started this: one callback missing one State."""
    short = copy.deepcopy(deps)
    victim = next(d for d in short if d.get("state"))
    victim["state"] = victim["state"][:-1]
    return short


# --------------------------------------------------------------------------
# 1. Primary signal: /healthz build
# --------------------------------------------------------------------------


@needs_node
def test_a_build_change_shows_the_sentence_on_the_next_navigation(tmp_path, served_deps):
    """The acceptance shape: a tab holding a graph one State short after a
    build change. On production the build key carries it; the graph is not
    fetched at all."""
    a = {"ok": True, "build": "aaaaaaa"}
    b = {"ok": True, "build": "bbbbbbb"}
    got = _run(tmp_path, [
        {"pathname": "/", "healthz": a, "deps": served_deps},
        {"pathname": "/props", "healthz": a, "deps": served_deps},
        {"pathname": "/ar", "healthz": b, "deps": _one_state_short(served_deps)},
    ])
    load, same, deployed = got
    assert load["baseline"] == {"kind": "build", "value": "aaaaaaa"}
    assert _silent(load), "load records; it never judges"
    assert _silent(same), "a navigation with no deploy shows nothing"
    assert _shown(deployed), deployed["r"]
    assert deployed["r"][3] == "yellow"


@needs_node
def test_one_small_get_per_navigation_and_none_on_load_beyond_the_record(tmp_path, served_deps):
    a = {"ok": True, "build": "aaaaaaa"}
    got = _run(tmp_path, [
        {"pathname": "/", "healthz": a, "deps": served_deps},
        {"pathname": "/x", "healthz": a, "deps": served_deps},
        {"pathname": "/y", "healthz": a, "deps": served_deps},
    ])
    assert [s["fetched"] for s in got] == [["/healthz"]] * 3, (
        "with a build key, every step is exactly one /healthz and never the "
        "28 KB graph"
    )


@needs_node
def test_once_stale_it_stops_asking(tmp_path, served_deps):
    got = _run(tmp_path, [
        {"pathname": "/", "healthz": {"build": "a"}, "deps": served_deps},
        {"pathname": "/x", "healthz": {"build": "b"}, "deps": served_deps},
        {"pathname": "/y", "healthz": {"build": "b"}, "deps": served_deps},
    ])
    assert _shown(got[1])
    assert got[2]["fetched"] == [], "said once; a stale tab makes no more requests"
    assert _silent(got[2]), "and does not re-send what is already on screen"


# --------------------------------------------------------------------------
# 2. Fallback: build null or absent — every local run
# --------------------------------------------------------------------------


@needs_node
@pytest.mark.parametrize("healthz", [{"ok": True}, {"ok": True, "build": None}],
                         ids=["build-absent", "build-null"])
def test_the_fallback_catches_a_graph_one_state_short(tmp_path, served_deps, healthz):
    got = _run(tmp_path, [
        {"pathname": "/", "healthz": healthz, "deps": _one_state_short(served_deps)},
        {"pathname": "/x", "healthz": healthz, "deps": _one_state_short(served_deps)},
        {"pathname": "/y", "healthz": healthz, "deps": served_deps},
    ])
    load, same, restarted = got
    assert load["baseline"]["kind"] == "graph"
    assert load["fetched"] == ["/healthz", "/_dash-dependencies"], (
        "the record tries the build first and falls back once"
    )
    assert _silent(same), "an unchanged graph shows nothing"
    assert same["fetched"] == ["/_dash-dependencies"], "one GET per navigation"
    assert _shown(restarted), "a State added server-side is a stale tab"


@needs_node
def test_the_fallback_is_order_independent(tmp_path, served_deps):
    """A restart that changes nothing may serve the same graph in another
    order; that must not read as a change."""
    shuffled = list(reversed(served_deps))
    got = _run(tmp_path, [
        {"pathname": "/", "healthz": {}, "deps": served_deps},
        {"pathname": "/x", "healthz": {}, "deps": shuffled},
    ])
    assert _silent(got[1])


@needs_node
def test_two_fresh_boots_of_this_tree_fingerprint_identically(tmp_path, served_deps):
    """The false-alarm test that matters locally: restart the server with no
    code change, navigate, and see nothing. Measured across two real
    processes, because any per-process value in the served graph (a uuid, a
    set's order) would fire the guard on every restart."""
    second = in_fresh_app(_SERVED)
    assert len(second) == len(served_deps)
    got = _run(tmp_path, [
        {"pathname": "/", "healthz": {}, "deps": served_deps},
        {"pathname": "/x", "healthz": {}, "deps": second},
    ])
    assert got[0]["baseline"]["kind"] == "graph"
    assert _silent(got[1]), "a restart with no change must not say 'out of date'"


# --------------------------------------------------------------------------
# 3. Fails quiet, never loud
# --------------------------------------------------------------------------


@needs_node
@pytest.mark.parametrize("later", [
    {"healthz": "fail"},          # network error
    {"healthz": None},            # non-2xx
    {"healthz": {"ok": True}},    # mid-swap: the key reads empty
], ids=["network", "http-error", "mid-swap-empty"])
def test_a_probe_that_cannot_answer_says_nothing(tmp_path, served_deps, later):
    got = _run(tmp_path, [
        {"pathname": "/", "healthz": {"build": "a"}, "deps": served_deps},
        {"pathname": "/x", "deps": served_deps, **later},
        {"pathname": "/y", "healthz": {"build": "b"}, "deps": served_deps},
    ])
    assert _silent(got[1]), "no answer is not a verdict"
    assert got[1]["baseline"] == {"kind": "build", "value": "a"}, "baseline kept"
    assert _shown(got[2]), "and the next navigation still asks"


@needs_node
def test_a_load_that_cannot_record_tries_again_next_navigation(tmp_path, served_deps):
    got = _run(tmp_path, [
        {"pathname": "/", "healthz": "fail", "deps": "fail"},
        {"pathname": "/x", "healthz": {"build": "a"}, "deps": served_deps},
    ])
    assert got[0]["baseline"] is None and _silent(got[0])
    assert got[1]["baseline"] == {"kind": "build", "value": "a"}
    assert _silent(got[1]), "a late record is still a record, not a verdict"


# --------------------------------------------------------------------------
# 4. The Python twin, and the wiring
# --------------------------------------------------------------------------


@pytest.mark.parametrize("baseline,observed,expected", [
    (None, "a", "record"),
    (None, None, "quiet"),
    ({"kind": "build", "value": "a"}, "a", "quiet"),
    ({"kind": "build", "value": "a"}, "b", "stale"),
    ({"kind": "build", "value": "a"}, None, "quiet"),
    ({"kind": "graph", "value": "62:ab"}, "62:cd", "stale"),
    ({"kind": "build", "value": "a", "stale": True}, "b", "quiet"),
])
def test_the_python_twin(baseline, observed, expected):
    assert stale_tab.verdict(baseline, observed) == expected


def test_the_same_sentence_as_the_poll_guard():
    assert poll_guard.STALE_MESSAGE.startswith(stale_tab.STALE_MESSAGE.rstrip(".")), (
        "one condition, one sentence, wherever the page notices it"
    )
    assert "reload" in stale_tab.STALE_MESSAGE.lower(), "it must name the remedy"


def test_registered_clientside_on_the_shells_location():
    got = in_fresh_app(
        "keys = [k for k in app.callback_map if 'stale-tab-baseline.data' in k]\n"
        "spec = app.callback_map[keys[0]] if len(keys) == 1 else {}\n"
        "print('RESULT:' + json.dumps({'keys': keys,\n"
        "    'serverside': 'callback' in spec,\n"
        "    'inputs': [str(i) for i in spec.get('inputs', [])]}))\n"
    )
    assert len(got["keys"]) == 1, got["keys"]
    assert not got["serverside"], (
        "CLIENTSIDE is the point: it must run in a tab whose server callbacks "
        "no longer match"
    )
    assert "url" in json.dumps(got["inputs"]) and "pathname" in json.dumps(got["inputs"])
