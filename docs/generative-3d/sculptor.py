import json
import threading

from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib import build_stream, model_picker, sculptor, spend

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
        dcc.Interval(id="g3-poll", interval=700, disabled=True),
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
    return run_id, False, True, "block", True, True


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
    Input("g3-poll", "n_intervals"),
    State("g3-run", "data"),
    State("g3-prompt", "value"),
    prevent_initial_call=True,
)
def poll(_, run_id, prompt):
    """Drain the seam and render whatever has arrived.

    Every `part` event carries a COMPLETE `.glb` of the parts so far, so the
    viewer is re-pointed at each in turn and the sculpture assembles on screen.
    `take()` clears as it reads, so this never redraws what it already drew.

    The Interval stops the moment the run ends — on the `done` event, or on a
    `done` flag with no event, which is how a failed build reports itself.
    """
    idle = (no_update,) * 11
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
        manifest = final.get("manifest") or {}
        note = f"{manifest.get('name', 'Untitled')} — {manifest.get('notes', '')}"
        if final.get("notes"):
            note += "  ·  " + "; ".join(final["notes"])
        note += (
            f"  ·  {final.get('part_count', 0)} parts  ·  "
            + spend.actual_line(final.get("usd", 0.0), final.get("seconds", 0.0))
        )
        return (
            final.get("data_url") or latest_src,
            f"A generated 3D sculpture: {manifest.get('name', prompt)}",
            note, "indigo", False,
            json.dumps(manifest, indent=2),
            "", True, "none", False, False,
        )

    if state["done"]:
        return (
            no_update, no_update,
            state["reason"] or "The sculpt did not complete.",
            "yellow", False, no_update,
            "", True, "none", False, False,
        )

    return (
        latest_src, no_update, no_update, no_update, no_update, no_update,
        progress, no_update, no_update, no_update, no_update,
    )


model_picker.register("g3", action_ids=["g3-go"])


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
