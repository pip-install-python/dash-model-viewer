"""Progress events for a sculpt, readable from any worker.

WHY A STORE AND NOT A MODULE DICT
---------------------------------
The obvious implementation is a dict in module state, and it is wrong here for
a reason that is invisible in development: gunicorn's worker count defaults to
`int(os.environ.get("WEB_CONCURRENCY", 1))`, so it is set by the ENVIRONMENT,
not by this repo's Dockerfile CMD. Whether production runs one worker or four
is a dashboard value nobody in a session can read.

With more than one worker, a per-process buffer polled by `dcc.Interval` hangs
intermittently: roughly half the polls land on a worker that never saw the run
and report nothing, forever. That is the excalidraw E4 defect, verified by the
ops seat, and it is unpleasant precisely because it works perfectly on a
laptop.

So the events go to a small file-backed store. It costs no dependency —
`lib/page_visibility.py` already persists state to a file on this host — and it
is correct for one worker as well as four. If the worker count is later
measured at one, this becomes belt and braces rather than dead code.

THE SEAM
--------
`take()` is deliberately the only way a reader consumes events: it returns
what has accumulated and clears it. A poller calls it on a timer; a websocket
collector would call it on an event loop and push. Swapping transports
therefore changes who calls `take()` and nothing else, which is why the
transport question can stay open while this ships.

NOT AN ARCHIVE. Runs are pruned on write, and a run that nobody reads expires.
This is a progress channel, not a record of what was built.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

#: Where runs live. A tmpdir by default: these are seconds-lived progress
#: records, and putting them on a persistent disk would be a promise this
#: module does not make.
STORE_DIR = Path(
    os.environ.get("BUILD_STREAM_DIR", "") or (Path(tempfile.gettempdir()) / "dmv-build-stream")
)

#: A run older than this is dead — the client went away, or the worker did.
RUN_TTL_SECONDS = int(os.environ.get("BUILD_STREAM_TTL", "900"))

#: Bound on events held for one run. A build emits one event per part and the
#: part budget is 28, so this is generous; it exists so a runaway producer
#: cannot fill a disk.
MAX_EVENTS = 200


def _path(run_id: str) -> Path:
    # `run_id` is generated here and never taken from a request, but join it
    # defensively anyway: a store keyed by a caller-supplied string is a path
    # traversal waiting to be written by the next person.
    safe = "".join(c for c in run_id if c.isalnum() or c in "-_")
    if not safe:
        raise ValueError("invalid run id")
    return STORE_DIR / f"{safe}.json"


def _read(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None


def _write(path: Path, payload: Dict[str, Any]) -> None:
    """Atomic: write a sibling temp file, then rename over the target.

    A reader on another worker can arrive mid-write, and a half-written JSON
    file would surface as a parse error rather than as "nothing yet".
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def prune(now: Optional[float] = None) -> int:
    """Drop expired runs. Returns how many went."""
    now = time.time() if now is None else now
    if not STORE_DIR.exists():
        return 0
    dropped = 0
    for path in STORE_DIR.glob("*.json"):
        payload = _read(path)
        if payload is None or now - payload.get("started", 0) > RUN_TTL_SECONDS:
            path.unlink(missing_ok=True)
            dropped += 1
    return dropped


def new_run() -> str:
    run_id = uuid.uuid4().hex
    prune()
    _write(_path(run_id), {"started": time.time(), "events": [], "done": False})
    return run_id


def emit(run_id: str, event: Dict[str, Any]) -> None:
    """Append one event. Never raises into the build.

    A progress channel that can fail the thing it is reporting on is worse
    than no progress channel, so a store error is swallowed here — the build
    still completes and the page still gets its result the ordinary way.
    """
    try:
        path = _path(run_id)
        payload = _read(path) or {"started": time.time(), "events": [], "done": False}
        events: List[Dict[str, Any]] = payload.setdefault("events", [])
        if len(events) < MAX_EVENTS:
            events.append({**event, "at": time.time()})
        _write(path, payload)
    except (OSError, ValueError):
        pass


def finish(run_id: str, ok: bool = True, reason: str = "") -> None:
    try:
        path = _path(run_id)
        payload = _read(path) or {"started": time.time(), "events": []}
        payload["done"] = True
        payload["ok"] = ok
        payload["reason"] = reason
        _write(path, payload)
    except (OSError, ValueError):
        pass


def take(run_id: str) -> Dict[str, Any]:
    """THE SEAM. Everything since the last call, and whether the run is over.

    Returns `{"events": [...], "done": bool, "ok": bool, "reason": str}`.
    Consuming clears the events so a poller does not re-render what it has
    already drawn; `done` is sticky so a late poll still learns the outcome.

    A websocket collector replaces the CALLER of this function, not the
    function — which is why the transport can be chosen later.
    """
    try:
        path = _path(run_id)
    except ValueError:
        return {"events": [], "done": True, "ok": False, "reason": "invalid run id"}
    payload = _read(path)
    if payload is None:
        return {"events": [], "done": False, "ok": True, "reason": ""}
    events = payload.get("events", [])
    if events:
        payload["events"] = []
        try:
            _write(path, payload)
        except OSError:
            pass
    return {
        "events": events,
        "done": bool(payload.get("done")),
        "ok": bool(payload.get("ok", True)),
        "reason": payload.get("reason", ""),
    }
