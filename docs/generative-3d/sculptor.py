import json
import threading
from datetime import date

from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib import (build_stream, manifest, model_picker, poll_guard, sculptor,
                 spend)

IDEAS = [
    "a brutalist lighthouse at dusk, weathered concrete and one warm light",
    "a desert observatory, sandstone and brass, dish pointed at the sky",
    "a bonsai on a stone plinth, copper pot, moss",
    "a cathedral of stacked glass cubes lit from inside",
]

# A neutral studio environment plus a real shadow — generated art looks flat
# and grey without image-based lighting, which reads as "broken" rather than
# "dark". This is the one place the demo needs opinionated defaults.
VIEWER_ATTRS = {
    "environment-image": "neutral",
    "exposure": "1.1",
    "shadow-softness": "0.7",
}

component = html.Div(
    [
        # The run id, and the timer that reads it. `dcc.Interval` is the
        # POLLING collector: it drains `build_stream.take()`, which is the same
        # seam a websocket collector would read on an event loop. Choosing the
        # other transport later replaces this component and nothing else.
        #
        # The run id lives in a per-tab `dcc.Store`, so a run belongs to the
        # tab that started it — two tabs sculpting at once do not read each
        # other's parts.
        dcc.Store(id="g3-run"),
        dcc.Store(id="g3-manifest"),
        dcc.Download(id="g3-dl-json"),
        dcc.Download(id="g3-dl-glb"),
        *poll_guard.components("g3"),
        dmc.Group(
            model_picker.components("g3", sculptor.MODEL, w=260),
            mb="xs",
        ),
        dmc.Text(id="g3-model-status", size="xs", c="dimmed"),
        dmc.Text(id="g3-estimate", size="xs", c="dimmed", mb="xs"),
        dmc.Group(
            [
                dmc.TextInput(
                    id="g3-prompt",
                    placeholder="Describe a sculpture…",
                    value=IDEAS[0],
                    style={"flex": 1},
                ),
                dmc.Button("Sculpt", id="g3-go", variant="filled"),
            ],
            mb="xs",
            align="flex-end",
        ),
        dmc.Group(
            [
                dmc.Badge(idea.split(",")[0], id={"type": "g3-idea", "i": i},
                          variant="light", style={"cursor": "pointer"})
                for i, idea in enumerate(IDEAS)
            ],
            gap="xs",
            mb="sm",
        ),
        # The sculpt call takes several seconds. Without a visible busy state
        # the page looks broken — you click, nothing moves, and there is no way
        # to tell a slow call from a dead one. The overlay sits over the viewer
        # rather than replacing it, so the previous sculpture stays on screen
        # while the next one is composed.
        dmc.Box(
            pos="relative",
            children=[
                dmc.LoadingOverlay(
                    id="g3-busy",
                    visible=False,
                    zIndex=10,
                    overlayProps={"radius": "md", "blur": 2},
                    loaderProps={"type": "bars", "color": "indigo"},
                ),
                dmv.ModelViewer(
                    id="g3-viewer",
                    # Placeholder until the first sculpt: one primitive built by
                    # the same writer, so the page is never an empty box.
                    src=sculptor.to_data_url(
                        sculptor.build(
                            {
                                "parts": [
                                    {"shape": "torus", "name": "seed",
                                     "size": {"x": 1.2, "y": 0.1, "z": 0.24},
                                     "position": {"x": 0, "y": 0.6, "z": 0},
                                     "rotation": {"x": 90, "y": 0, "z": 0},
                                     "color": "#4C6EF5", "metallic": 0.9,
                                     "roughness": 0.25, "emissive_strength": 0.0},
                                ]
                            }
                        )[0]
                    ),
                    alt="A generated 3D sculpture",
                    camera_controls=True,
                    shadow_intensity=1,
                    interpolation_decay=90,
                    attributes=VIEWER_ATTRS,
                    style={"width": "100%", "height": "440px"},
                ),
            ],
        ),
        dmc.Text(
            # Measured, not guessed: a sculpt runs ~35s (effort="medium", and the
        # composition reasoning is the slow part). An estimate that is too
        # low is worse than none — the user concludes it has hung.
        "Composing — this takes about 30 to 45 seconds.",
            id="g3-working", size="sm", c="dimmed", mt="xs", display="none",
        ),
        dmc.Alert(id="g3-status", mt="sm", color="indigo", hide=True),
        dmc.Spoiler(
            id="g3-spoiler",
            showLabel="Show the parts list",
            hideLabel="Hide",
            maxHeight=0,
            children=dmc.Code(id="g3-json", block=True),
            mt="xs",
        ),
        dmc.Group(
            [
                dmc.Button("Save the manifest", id="g3-save-json",
                           variant="light", size="xs", disabled=True),
                dmc.Button("Download .glb", id="g3-save-glb",
                           variant="light", size="xs", disabled=True),
            ],
            gap="xs", mt="xs",
        ),
    ]
)


@callback(
    Output("g3-prompt", "value"),
    Input({"type": "g3-idea", "i": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def use_idea(clicks):
    if not any(clicks or []):
        return no_update
    return IDEAS[ctx.triggered_id["i"]]


@callback(
    Output("g3-run", "data"),
    Output("g3-poll", "disabled"),
    Output("g3-status", "hide"),
    Output("g3-working", "display"),
    Output("g3-go", "loading"),
    Output("g3-prompt", "disabled"),
    Output("g3-poll", "n_intervals"),
    Output("g3-alive", "data"),
    Input("g3-go", "n_clicks"),
    State("g3-prompt", "value"),
    State("g3-model", "value"),
    prevent_initial_call=True,
)
def start_sculpt(_, prompt, model):
    """Start the build and return immediately.

    This used to be the whole thing: one callback that blocked for ~35 seconds
    behind a loading overlay and then produced a finished object. The build now
    runs on a background thread and the poller reads parts as they assemble,
    which is the change the owner asked for.

    A plain thread suffices: the owner reports one gunicorn worker, and the
    store is file-backed regardless, so a later WEB_CONCURRENCY change on the
    dashboard cannot silently break the read side.
    """
    run_id = build_stream.new_run()
    threading.Thread(
        target=sculptor.sculpt_streaming,
        args=(run_id, prompt),
        kwargs={"model": model or sculptor.MODEL},
        daemon=True,
    ).start()
    # n_intervals back to 0 re-arms the capped Interval, so the ceiling
    # bounds THIS build rather than the tab's whole lifetime.
    return run_id, False, True, "block", True, True, 0, poll_guard.tick_value(0)


@callback(
    Output("g3-viewer", "src"),
    Output("g3-viewer", "alt"),
    Output("g3-status", "children"),
    Output("g3-status", "color"),
    Output("g3-status", "hide", allow_duplicate=True),
    Output("g3-json", "children"),
    Output("g3-working", "children"),
    Output("g3-poll", "disabled", allow_duplicate=True),
    Output("g3-working", "display", allow_duplicate=True),
    Output("g3-go", "loading", allow_duplicate=True),
    Output("g3-prompt", "disabled", allow_duplicate=True),
    Output("g3-manifest", "data"),
    Output("g3-save-json", "disabled"),
    Output("g3-save-glb", "disabled"),
    Output("g3-alive", "data", allow_duplicate=True),
    Input("g3-poll", "n_intervals"),
    State("g3-run", "data"),
    State("g3-model", "value"),
    State("g3-prompt", "value"),
    prevent_initial_call=True,
)
def poll(tick, run_id, model, prompt):
    """Drain the seam and render whatever has arrived.

    Every `part` event carries a COMPLETE `.glb` of the parts so far, so the
    viewer is re-pointed at each in turn and the sculpture assembles on screen.
    `take()` clears as it reads, so this never redraws what it already drew.

    The Interval stops the moment the run ends — on the `done` event, or on a
    `done` flag with no event, which is how a failed build reports itself.

    The parameter ORDER follows the State order above — `g3-model` then
    `g3-prompt`. It did not: the two were transposed, so the provenance
    written into every exported manifest had the model id under "prompt"
    and the prompt text under "model". The suite missed it because the
    tests call this function directly, in ITS order, never through the
    wiring — `tests/test_callback_wiring.py` now compares the two.
    """
    alive = poll_guard.tick_value(tick)
    idle = (no_update,) * 14 + (alive,)
    if not run_id:
        return idle

    state = build_stream.take(run_id)

    latest_src = no_update
    progress = no_update
    final = None
    for event in state["events"]:
        phase = event.get("phase")
        if phase == "part":
            latest_src = event["data_url"]
            progress = f"Building — part {event['index']} of {event['total']}"
        elif phase == "assembling":
            progress = (
                f"Composed in {event.get('seconds', 0)}s — "
                f"assembling {event['total']} parts"
            )
        elif phase == "done":
            final = event

    if final is not None:
        # NOT named `manifest` — that is the module, imported above, and
        # shadowing it here would turn `manifest.from_scene` into a dict lookup.
        scene = final.get("manifest") or {}
        note = f"{scene.get('name', 'Untitled')} — {scene.get('notes', '')}"
        if final.get("notes"):
            note += "  ·  " + "; ".join(final["notes"])
        note += (
            f"  ·  {final.get('part_count', 0)} parts  ·  "
            + spend.actual_line(final.get("usd", 0.0), final.get("seconds", 0.0))
        )
        return (
            final.get("data_url") or latest_src,
            f"A generated 3D sculpture: {scene.get('name', prompt)}",
            note, "indigo", False,
            json.dumps(scene, indent=2),
            "", True, "none", False, False,
            manifest.from_scene(scene, {
                "prompt": prompt, "model": model,
                "usd": final.get("usd", 0.0),
                "generated": date.today().isoformat(),
            }), False, False, alive,
        )

    if state["done"]:
        return (
            no_update, no_update,
            state["reason"] or "The sculpt did not complete.",
            "yellow", False, no_update,
            "", True, "none", False, False,
            no_update, no_update, no_update, alive,
        )

    return (
        latest_src, no_update, no_update, no_update, no_update, no_update,
        progress, no_update, no_update, no_update, no_update,
        no_update, no_update, no_update, alive,
    )


model_picker.register("g3", action_ids=["g3-go"])
poll_guard.register("g3", "g3-status", resets=[
    ("g3-working", "display", "none"),
    ("g3-go", "loading", False),
    ("g3-prompt", "disabled", False),
])


@callback(
    Output("g3-estimate", "children"),
    Input("g3-model", "value"),
)
def show_estimate(model):
    """Priced BEFORE the button, and re-priced when the model changes.

    A visitor choosing Opus over Haiku is choosing a 5x bill, and the only
    moment that fact is useful is before the click.
    """
    return spend.estimate_line(model or sculptor.MODEL, sculptor.MAX_TOKENS)


@callback(
    Output("g3-dl-json", "data"),
    Input("g3-save-json", "n_clicks"),
    State("g3-manifest", "data"),
    prevent_initial_call=True,
)
def save_manifest(_clicks, stored):
    """The manifest is the valuable half.

    Re-importing it on [Scene Manifest](/scene-manifest) re-renders the same
    sculpture for free, and editing it costs nothing — which is the whole point
    of keeping it rather than only the `.glb`.
    """
    if not stored:
        return no_update
    try:
        m = manifest.validate(stored)
    except manifest.ManifestError:
        return no_update
    return {"content": manifest.dumps(m),
             "filename": manifest.filename(m, "json")}


@callback(
    Output("g3-dl-glb", "data"),
    Input("g3-save-glb", "n_clicks"),
    State("g3-manifest", "data"),
    prevent_initial_call=True,
)
def save_glb(_clicks, stored):
    """Rebuilt from the stored manifest on demand, not carried as bytes.

    `lib/glb.py` is deterministic, so this is the same file the viewer is
    showing — and it keeps a megabyte of binary out of the browser's store.
    Nothing is written to disk at any point.

    Two callbacks rather than one dispatching on `ctx.triggered_id`: a callback
    that reads the context cannot be called from a test, and these two are
    worth testing.
    """
    if not stored:
        return no_update
    try:
        m = manifest.validate(stored)
        data, _notes, _used = manifest.render(m)
    except manifest.ManifestError:
        return no_update
    return dcc.send_bytes(data, manifest.filename(m, "glb"))
