"""Does each callback's parameter order match the order Dash wires into it?

THE BUG THIS EXISTS FOR
-----------------------
/generative-3d's poll declared `State("g3-model")` then `State("g3-prompt")` and
received them as `(prompt, model)`. The two were transposed, so every manifest
exported from that page recorded the model id under "prompt" and the user's
prompt text under "model". Nothing crashed; the sculpture was correct; only the
provenance — the part a file keeps after the session is gone — was wrong.

THE SUITE MISSED IT BECAUSE THE SUITE CALLED THE FUNCTION, NOT THE CALLBACK.
`tests/test_downloads.py` passed its arguments in the FUNCTION's order, so the
transposition cancelled out and the assertion `provenance["model"] ==
"claude-opus-5"` passed while the page wrote the opposite. A test that reproduces
the wiring is the only kind that can see this.

WHY A "SWAP" AND NOT A NAME MATCH
---------------------------------
Requiring every parameter to be named after its component is far too noisy to be
a gate: measured across this app, 33 pairs differ innocently, because a parameter
is often named after the PROPERTY (`tx-upload` → `contents`) or for the reader
(`url` → `pathname`). The precise signal is a TRANSPOSITION — a parameter that
matches a DIFFERENT dependency of the same callback. Measured over 43 callbacks,
that rule fires on exactly one, and it is the real bug.
"""

from __future__ import annotations

import inspect

import pytest

from conftest import in_fresh_app


def _tail(component_id):
    """The distinguishing part of an id: `g3-model` → `model`."""
    if not isinstance(component_id, str):
        return None          # a pattern-matching dict id carries no name here
    return component_id.split("-")[-1].lower()


def swaps(app):
    """Every transposed pair, and how many callbacks were actually compared.

    Returns (hits, compared) so a caller can prove the sweep swept something —
    a sweep that found nothing and a sweep that read nothing are the same green.
    """
    hits = []
    compared = 0
    for spec in app.callback_map.values():
        function = spec.get("callback")
        if function is None:
            continue                      # clientside: no Python signature
        function = inspect.unwrap(function)
        try:
            params = [p.lower() for p in inspect.signature(function).parameters]
        except (TypeError, ValueError):
            continue
        deps = list(spec["inputs"]) + list(spec.get("state", []))
        tails = [_tail(d["id"]) for d in deps]
        if len(tails) != len(params):
            continue                      # grouped/flexible signatures
        compared += 1
        for i, (tail_i, param_i) in enumerate(zip(tails, params)):
            for j, (tail_j, param_j) in enumerate(zip(tails, params)):
                if i == j or not tail_i or not tail_j:
                    continue
                if tail_j in param_i and tail_i in param_j and tail_i not in param_i:
                    hits.append(
                        f"{function.__module__}.{function.__name__}: "
                        f"'{tail_i}' is wired into '{param_i}' while "
                        f"'{tail_j}' is wired into '{param_j}'"
                    )
    return hits, compared


def test_no_callback_in_this_app_has_transposed_parameters():
    """THE GATE. It caught /generative-3d's poll; it is here so the next one is
    caught by a machine rather than by reading."""
    # Swept in a pristine interpreter: Dash drains its registrations into the
    # first app to set up a server, so in-session `callback_map` depends on test
    # order — measured at 2 callbacks instead of 43. See conftest.in_fresh_app.
    got = in_fresh_app(
        "sys.path.insert(0, os.path.join(os.getcwd(), 'tests'))\n"
        "import test_callback_wiring as m\n"
        "hits, compared = m.swaps(app)\n"
        "print('RESULT:' + json.dumps({'hits': hits, 'compared': compared}))\n"
    )
    hits, compared = got["hits"], got["compared"]
    assert compared >= 40, (
        f"only {compared} callbacks compared — the sweep is not reading the app, "
        f"and a clean result would mean nothing"
    )
    assert not hits, "transposed callback parameters:\n  " + "\n  ".join(sorted(set(hits)))


def test_the_sweep_can_see_a_transposition_when_there_is_one():
    """The negative control. A sweep that cannot fail is not evidence, and this
    one's rule is narrow enough to be worth proving on a known-bad case."""

    def poll(tick, run_id, prompt, model):      # the bug, as it was written
        return tick, run_id, prompt, model

    fake = type("App", (), {"callback_map": {
        "k": {
            "callback": poll,
            "inputs": [{"id": "g3-poll", "property": "n_intervals"}],
            "state": [{"id": "g3-run", "property": "data"},
                      {"id": "g3-model", "property": "value"},
                      {"id": "g3-prompt", "property": "value"}],
        }
    }})()
    hits, compared = swaps(fake)
    assert compared == 1
    assert hits, "the rule failed to flag the exact bug it was written for"
    assert "'model' is wired into 'prompt'" in hits[0]


def test_the_sweep_does_not_flag_a_parameter_named_for_its_property():
    """The common innocent case — `Input("tx-upload", "contents")` received as
    `contents`. If this tripped, the gate would need an allow-list, and an
    allow-list of thirty entries is worse than the bug."""

    def accept(contents, filename):
        return contents, filename

    fake = type("App", (), {"callback_map": {
        "k": {
            "callback": accept,
            "inputs": [{"id": "tx-upload", "property": "contents"}],
            "state": [{"id": "tx-upload", "property": "filename"}],
        }
    }})()
    hits, compared = swaps(fake)
    assert compared == 1
    assert not hits, f"false positive: {hits}"


# --------------------------------------------------------------------------
# The specific fix, pinned where a reader will look for it
# --------------------------------------------------------------------------


@pytest.mark.parametrize("module,expected", [
    ("docs.generative-3d.sculptor", ["tick", "run_id", "model", "prompt"]),
    ("docs.sculpt-from-image.sculpt_from_image", ["tick", "run_id", "model", "hint"]),
])
def test_both_polls_take_the_model_before_the_free_text(module, expected):
    """The two pages are deliberately the same shape now. /generative-3d was the
    odd one out, and being the odd one out is how it went unnoticed."""
    import importlib

    poll = importlib.import_module(module).poll
    assert list(inspect.signature(poll).parameters) == expected


def test_generative_3d_provenance_is_the_right_way_round():
    """The consequence, asserted end to end: drive the page's own poll through a
    finished run and read the provenance it stores."""
    import importlib

    from lib import build_stream

    page = importlib.import_module("docs.generative-3d.sculptor")
    run_id = build_stream.new_run()
    build_stream.emit(run_id, {
        "phase": "done", "total": 1, "data_url": "data:model/gltf-binary;base64,ZZZ",
        "manifest": {"name": "Lighthouse", "notes": "", "parts": [{
            "name": "tower", "shape": "cylinder",
            "size": {"x": 0.4, "y": 2.0, "z": 0.4},
            "position": {"x": 0, "y": 1.0, "z": 0},
            "rotation": {"x": 0, "y": 0, "z": 0},
            "color": "#E8E4DC", "metallic": 0.0,
            "roughness": 0.8, "emissive_strength": 0.0,
        }]},
        "notes": [], "part_count": 1, "seconds": 3.0, "usd": 0.01,
    })
    build_stream.finish(run_id, ok=True)

    returned = page.poll(1, run_id, "claude-opus-5", "a tall lighthouse")
    stored = next(v for v in returned if isinstance(v, dict) and "parts" in v)
    provenance = stored["provenance"]
    assert provenance["model"] == "claude-opus-5", "the model id belongs in 'model'"
    assert provenance["prompt"] == "a tall lighthouse", "and the text in 'prompt'"


# --------------------------------------------------------------------------
# The renderer's own rule, which the server does not enforce
# --------------------------------------------------------------------------


def qualified_outputs(app):
    """Every (output, writer) pair, keyed the way the BROWSER keys them.

    `allow_duplicate` lets two callbacks write the same property, and Dash
    tells them apart by appending a hash OF THE CALLBACK'S INPUTS — nothing
    else. So two callbacks with the same input list writing the same property
    produce the SAME qualified id, and the renderer rejects the graph with
    "Duplicate callback outputs".
    """
    from collections import defaultdict

    seen = defaultdict(list)
    for key, spec in app.callback_map.items():
        outputs = key.strip(".").split("...") if key.startswith("..") else [key]
        writer = getattr(spec.get("callback"), "__name__", "<clientside>")
        for output in outputs:
            seen[output].append(writer)
    return seen


def test_no_two_callbacks_declare_the_same_qualified_output():
    """THE GATE, and it is here because this shipped.

    `lib/poll_guard`'s stale guard had `-poll.n_intervals` as its only Input —
    exactly the poll's — so every property the two shared collided: nine
    duplicates across /sculpt-from-image and /generative-3d. The server
    registers such a graph happily; only the RENDERER refuses it, and only
    visibly with dev tools on, so it reached production looking healthy and
    broke the moment the owner set `debug=True`.

    The fix was to read the liveness store as an Input rather than a State,
    which changes the input list and so the hash.
    """
    got = in_fresh_app(
        "from collections import defaultdict\n"
        "seen = defaultdict(list)\n"
        "for key, spec in app.callback_map.items():\n"
        "    outs = key.strip('.').split('...') if key.startswith('..') else [key]\n"
        "    writer = getattr(spec.get('callback'), '__name__', '<clientside>')\n"
        "    for o in outs:\n"
        "        seen[o].append(writer)\n"
        "print('RESULT:' + json.dumps({'total': len(seen),\n"
        "      'dupes': {o: w for o, w in seen.items() if len(w) > 1}}))\n"
    )
    assert got["total"] > 100, (
        f"only {got['total']} outputs seen — the sweep is not reading the app"
    )
    assert not got["dupes"], (
        "two callbacks write the same qualified output; the renderer will "
        "refuse this graph:\n  " + "\n  ".join(
            f"{o} <- {w}" for o, w in got["dupes"].items())
    )


def test_the_stale_guard_and_the_poll_do_not_share_an_input_list():
    """The specific shape, pinned where a reader will look for it: these two
    write the same properties, so their input lists must differ or their
    outputs collide."""
    import hashlib

    from lib import poll_guard

    assert "Input(f\"{prefix}-alive\", \"data\")" in inspect.getsource(poll_guard.register)

    def digest(inputs):
        return hashlib.sha256(".".join(inputs).encode()).hexdigest()

    poll_inputs = ["<Input `si-poll.n_intervals`>"]
    guard_inputs = poll_inputs + ["<Input `si-alive.data`>"]
    assert digest(poll_inputs) != digest(guard_inputs)
