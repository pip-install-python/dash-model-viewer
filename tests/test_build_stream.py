"""The progress channel, exercised with no socket and no model call.

The transport is deliberately not under test here — there isn't one yet.
`take()` is the seam a poller or a websocket collector both sit behind, so
these tests pin the seam's contract and leave the choice open.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from lib import build_stream


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(build_stream, "STORE_DIR", tmp_path / "runs")
    yield


def test_a_new_run_starts_empty_and_unfinished():
    run = build_stream.new_run()
    assert build_stream.take(run) == {
        "events": [], "done": False, "ok": True, "reason": ""
    }


def test_events_come_back_in_order():
    run = build_stream.new_run()
    for i in range(3):
        build_stream.emit(run, {"phase": "part", "index": i})
    events = build_stream.take(run)["events"]
    assert [e["index"] for e in events] == [0, 1, 2]


def test_take_clears_so_a_poller_does_not_redraw():
    run = build_stream.new_run()
    build_stream.emit(run, {"phase": "part", "index": 1})
    assert len(build_stream.take(run)["events"]) == 1
    assert build_stream.take(run)["events"] == [], "take must consume"


def test_done_is_sticky_so_a_late_poll_still_learns_the_outcome():
    """The last events and `done` can arrive in the same take, or the client
    can poll once more after everything. Both must report the outcome."""
    run = build_stream.new_run()
    build_stream.emit(run, {"phase": "part", "index": 1})
    build_stream.finish(run, ok=True)
    first = build_stream.take(run)
    assert first["events"] and first["done"] is True
    second = build_stream.take(run)
    assert second["events"] == [] and second["done"] is True


def test_a_failed_run_carries_its_reason():
    run = build_stream.new_run()
    build_stream.finish(run, ok=False, reason="the model declined")
    state = build_stream.take(run)
    assert state["done"] is True and state["ok"] is False
    assert state["reason"] == "the model declined"


# --------------------------------------------------------------------------
# The cross-worker property — the whole reason this is not a module dict
# --------------------------------------------------------------------------


def test_a_second_PROCESS_reads_what_the_first_wrote(tmp_path):
    """Two real processes, standing in for two gunicorn workers.

    A per-process buffer polled by dcc.Interval hangs intermittently when
    WEB_CONCURRENCY > 1: half the polls land on a worker that never saw the
    run. That defect is invisible on a laptop, so it gets a test that actually
    crosses a process boundary — `importlib.reload` does NOT, because it
    mutates the existing module object in place and hands back the same one.
    """
    import os
    import subprocess
    import sys

    store = tmp_path / "shared"
    env = {**os.environ, "BUILD_STREAM_DIR": str(store)}
    repo = str(Path(__file__).resolve().parent.parent)

    write = subprocess.run(
        [sys.executable, "-c",
         "from lib import build_stream as b;"
         "r = b.new_run();"
         "b.emit(r, {'phase': 'part', 'index': 7});"
         "print(r)"],
        capture_output=True, text=True, env=env, cwd=repo, check=True,
    )
    run_id = write.stdout.strip()

    read = subprocess.run(
        [sys.executable, "-c",
         f"from lib import build_stream as b;"
         f"print(b.take('{run_id}')['events'])"],
        capture_output=True, text=True, env=env, cwd=repo, check=True,
    )
    assert "'index': 7" in read.stdout, (
        f"a second process must see the first's events; got {read.stdout!r}"
    )


def test_reader_never_sees_a_half_written_file():
    """Writes go via a temp file and os.replace, so a reader arriving
    mid-write sees the previous complete state, not a parse error."""
    run = build_stream.new_run()
    build_stream.emit(run, {"phase": "part", "index": 1})
    path = build_stream._path(run)
    assert json.loads(path.read_text())["events"], "file must be valid JSON at rest"
    leftovers = list(Path(path.parent).glob("*.tmp"))
    assert not leftovers, f"temp files left behind: {leftovers}"


# --------------------------------------------------------------------------
# Bounds and failure
# --------------------------------------------------------------------------


def test_events_are_bounded():
    run = build_stream.new_run()
    for i in range(build_stream.MAX_EVENTS + 50):
        build_stream.emit(run, {"i": i})
    assert len(build_stream.take(run)["events"]) == build_stream.MAX_EVENTS


def test_expired_runs_are_pruned():
    run = build_stream.new_run()
    path = build_stream._path(run)
    payload = json.loads(path.read_text())
    payload["started"] = time.time() - build_stream.RUN_TTL_SECONDS - 1
    path.write_text(json.dumps(payload))
    assert build_stream.prune() == 1
    assert not path.exists()


def test_emit_never_raises_into_the_build(monkeypatch):
    """A progress channel that can fail the thing it reports on is worse than
    no progress channel."""
    run = build_stream.new_run()

    def explode(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(build_stream, "_write", explode)
    build_stream.emit(run, {"phase": "part"})     # must not raise
    build_stream.finish(run, ok=True)             # must not raise


def test_take_on_an_unknown_run_is_not_an_error():
    assert build_stream.take("nosuchrun")["events"] == []


def test_a_traversal_shaped_run_id_cannot_escape_the_store():
    """The id is generated here and never taken from a request, but the store
    is keyed by a string and the next person to touch it may not know that.

    The sanitiser strips separators rather than raising, so the observable
    property is not "refused" — it is that the resolved path stays inside
    STORE_DIR. Assert that, not the error I first assumed."""
    path = build_stream._path("../../etc/passwd")
    assert path.parent == build_stream.STORE_DIR
    assert ".." not in str(path)
    # and reading it is simply an unknown run, not an error and not a file read
    assert build_stream.take("../../etc/passwd")["events"] == []

    with pytest.raises(ValueError):
        build_stream._path("../..")          # nothing survives sanitising


# --------------------------------------------------------------------------
# The emitter — no socket, no model call, no spend
# --------------------------------------------------------------------------


def _scene(n):
    part = lambda i: {                                    # noqa: E731
        "name": f"part{i}", "shape": "box",
        "size": {"x": 0.3, "y": 0.3, "z": 0.3},
        "position": {"x": 0.0, "y": 0.2, "z": 0.0},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
        "color": "#C8A24B", "metallic": 0.1,
        "roughness": 0.6, "emissive_strength": 0.0,
    }
    return {"name": "test", "notes": "", "parts": [part(i) for i in range(n)]}


def test_streaming_emits_one_part_event_per_part(monkeypatch):
    from lib import sculptor

    scene = _scene(4)
    monkeypatch.setattr(
        sculptor, "sculpt",
        lambda *a, **k: sculptor.SculptResult(
            ok=True, manifest=scene, part_count=4, seconds=1.0
        ),
    )
    run = build_stream.new_run()
    sculptor.sculpt_streaming(run, "a lighthouse")
    state = build_stream.take(run)

    phases = [e["phase"] for e in state["events"]]
    assert phases[0] == "asking"
    assert phases[1] == "assembling"
    assert phases.count("part") == 4, "one event per part"
    assert phases[-1] == "done"
    assert state["done"] is True and state["ok"] is True


def test_each_part_event_carries_a_progressively_larger_model(monkeypatch):
    """The point of streaming: every event is a real, complete .glb of the
    parts so far, so the viewer shows the sculpture appearing piece by piece
    rather than a spinner and then a finished object."""
    from lib import sculptor

    monkeypatch.setattr(
        sculptor, "sculpt",
        lambda *a, **k: sculptor.SculptResult(ok=True, manifest=_scene(3), part_count=3),
    )
    run = build_stream.new_run()
    sculptor.sculpt_streaming(run, "x")
    parts = [e for e in build_stream.take(run)["events"] if e["phase"] == "part"]

    assert [p["index"] for p in parts] == [1, 2, 3]
    for p in parts:
        assert p["data_url"].startswith("data:model/gltf-binary;base64,")
    sizes = [len(p["data_url"]) for p in parts]
    assert sizes == sorted(sizes), "each step should contain at least as much"
    assert sizes[0] < sizes[-1], "and the last must be bigger than the first"


def test_streaming_charges_ONCE_not_per_part(monkeypatch):
    """Streaming adds no model calls. The model returns the whole parts list in
    a single response; what is streamed is the ASSEMBLY of it. Emitting per
    part must never become charging per part."""
    from lib import sculptor, spend

    calls = []
    monkeypatch.setattr(spend, "record", lambda *a, **k: calls.append(a) or 0.0)
    monkeypatch.setattr(
        sculptor, "sculpt",
        lambda *a, **k: sculptor.SculptResult(ok=True, manifest=_scene(6), part_count=6),
    )
    run = build_stream.new_run()
    sculptor.sculpt_streaming(run, "x")

    assert len(calls) == 0, (
        "sculpt_streaming must delegate the single metered call to sculpt(), "
        "not meter anything itself"
    )


def test_a_failed_sculpt_finishes_the_run_with_its_reason(monkeypatch):
    from lib import sculptor

    monkeypatch.setattr(
        sculptor, "sculpt",
        lambda *a, **k: sculptor.SculptResult(ok=False, reason="no key"),
    )
    run = build_stream.new_run()
    sculptor.sculpt_streaming(run, "x")
    state = build_stream.take(run)
    assert state["done"] is True and state["ok"] is False
    assert state["reason"] == "no key"
    assert [e["phase"] for e in state["events"]][-1] == "failed"


# --------------------------------------------------------------------------
# The poller — the collector that sits on the seam today
# --------------------------------------------------------------------------


def _page():
    import importlib
    return importlib.import_module("docs.generative-3d.sculptor")


def test_the_interval_keeps_running_mid_build():
    page = _page()
    run = build_stream.new_run()
    build_stream.emit(run, {
        "phase": "part", "index": 2, "total": 5,
        "data_url": "data:model/gltf-binary;base64,AAA",
    })
    out = page.poll(1, run, "x")
    assert out[0] == "data:model/gltf-binary;base64,AAA", "viewer follows the parts"
    assert "part 2 of 5" in out[6]
    assert out[7] is not True, "the Interval must keep polling while building"


def test_the_interval_STOPS_when_the_run_finishes():
    """A timer left running after the build is a request every 700ms, forever,
    for as long as the tab is open."""
    page = _page()
    run = build_stream.new_run()
    build_stream.emit(run, {
        "phase": "done", "total": 1, "data_url": "data:model/gltf-binary;base64,ZZZ",
        "manifest": {"name": "Tower", "notes": "a tower"}, "notes": [],
        "part_count": 1, "seconds": 3.2, "usd": 0.01,
    })
    build_stream.finish(run, ok=True)
    out = page.poll(9, run, "x")
    assert out[7] is True, "the Interval must stop on done"
    assert out[0] == "data:model/gltf-binary;base64,ZZZ"
    assert "Tower" in out[2]
    assert out[9] is False and out[10] is False, "button and input re-enabled"


def test_the_interval_stops_on_a_failed_run():
    page = _page()
    run = build_stream.new_run()
    build_stream.finish(run, ok=False, reason="ANTHROPIC_API_KEY is not set")
    out = page.poll(3, run, "x")
    assert out[7] is True, "a failed run must stop the timer too"
    assert "ANTHROPIC_API_KEY" in out[2]
    assert out[3] == "yellow"


def test_a_run_belongs_to_the_tab_that_started_it():
    """The run id lives in a per-tab dcc.Store, so two tabs sculpting at once
    read their own parts. Polling someone else's id yields their events, which
    is why the id is a server-generated uuid and never a guessable key."""
    page = _page()
    mine = build_stream.new_run()
    theirs = build_stream.new_run()
    build_stream.emit(theirs, {
        "phase": "part", "index": 1, "total": 2,
        "data_url": "data:model/gltf-binary;base64,THEIRS",
    })
    out = page.poll(1, mine, "x")
    assert out[0] != "data:model/gltf-binary;base64,THEIRS"
    assert len(mine) == 32 and mine != theirs, "ids are distinct uuids"


def test_poll_without_a_run_id_does_nothing():
    page = _page()
    assert len(page.poll(1, None, "x")) == 11
