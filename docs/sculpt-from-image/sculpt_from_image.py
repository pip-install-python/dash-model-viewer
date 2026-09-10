import json
import threading

from dash import Input, Output, State, callback, dcc, html, no_update
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib import build_stream, sculptor, spend, uploads

#: 4 MB, the same cap /texture-upload states, from the same module. A vision
#: model resizes anything larger anyway, so a bigger allowance would buy a
#: slower upload and no more detail.
MAX_IMAGE_BYTES = 4 * 1024 * 1024

VIEWER_ATTRS = {
    "environment-image": "neutral",
    "exposure": "1.1",
    "shadow-softness": "0.7",
}

component = html.Div(
    [
        dcc.Store(id="si-image"),
        dcc.Store(id="si-run"),
        dcc.Interval(id="si-poll", interval=700, disabled=True),
        dmc.Group(
            [
                dcc.Upload(
                    id="si-upload",
                    accept="image/png,image/jpeg",
                    multiple=False,
                    children=dmc.Button("Choose an image (PNG or JPEG)"),
                ),
                dmc.TextInput(
                    id="si-hint",
                    placeholder="Optional: a nudge, e.g. 'emphasise the arches'",
                    style={"flex": 1},
                ),
                dmc.Button("Sculpt it", id="si-go", variant="filled", disabled=True),
            ],
            mb="xs",
            align="flex-end",
        ),
        dmc.Text(id="si-upload-status", size="sm", c="dimmed", mb="xs"),
        dmc.Grid(
            gutter="md",
            children=[
                dmc.GridCol(
                    dmc.Paper(
                        withBorder=True,
                        p="xs",
                        children=[
                            dmc.Text("Your image", size="xs", c="dimmed", mb=4),
                            html.Img(
                                id="si-preview",
                                style={"width": "100%", "borderRadius": "6px"},
                            ),
                        ],
                    ),
                    span={"base": 12, "md": 5},
                ),
                dmc.GridCol(
                    dmv.ModelViewer(
                        id="si-viewer",
                        src=sculptor.to_data_url(
                            sculptor.build(
                                {
                                    "parts": [
                                        {"shape": "box", "name": "seed",
                                         "size": {"x": 0.9, "y": 0.9, "z": 0.9},
                                         "position": {"x": 0, "y": 0.45, "z": 0},
                                         "rotation": {"x": 0, "y": 25, "z": 0},
                                         "color": "#4C6EF5", "metallic": 0.8,
                                         "roughness": 0.3, "emissive_strength": 0.0},
                                    ]
                                }
                            )[0]
                        ),
                        alt="A sculpture generated from an uploaded image",
                        camera_controls=True,
                        shadow_intensity=1,
                        interpolation_decay=90,
                        attributes=VIEWER_ATTRS,
                        style={"width": "100%", "height": "420px"},
                    ),
                    span={"base": 12, "md": 7},
                ),
            ],
        ),
        dmc.Text(id="si-working", size="sm", c="dimmed", mt="xs", display="none"),
        dmc.Alert(id="si-status", mt="sm", color="indigo", hide=True),
        dmc.Spoiler(
            id="si-spoiler",
            showLabel="Show the parts list",
            hideLabel="Hide",
            maxHeight=0,
            children=dmc.Code(id="si-json", block=True),
            mt="xs",
        ),
    ]
)


@callback(
    Output("si-image", "data"),
    Output("si-upload-status", "children"),
    Output("si-preview", "src"),
    Output("si-go", "disabled"),
    Input("si-upload", "contents"),
    State("si-upload", "filename"),
    prevent_initial_call=True,
)
def accept_image(contents, filename):
    """Validate, preview, and enable the button. Nothing reaches disk."""
    raw, _media_type, message = uploads.decode_image(
        contents, filename, max_bytes=MAX_IMAGE_BYTES
    )
    if raw is None:
        return None, message, no_update, True
    return contents, f"{message} — ready.", contents, False


@callback(
    Output("si-run", "data"),
    Output("si-poll", "disabled"),
    Output("si-status", "hide"),
    Output("si-working", "display"),
    Output("si-go", "loading"),
    Input("si-go", "n_clicks"),
    State("si-image", "data"),
    State("si-hint", "value"),
    prevent_initial_call=True,
)
def start(_, image, hint):
    if not image:
        return no_update, no_update, no_update, no_update, no_update
    run_id = build_stream.new_run()
    threading.Thread(
        target=sculptor.sculpt_image_streaming,
        args=(run_id, image, hint or ""),
        daemon=True,
    ).start()
    return run_id, False, True, "block", True


@callback(
    Output("si-viewer", "src"),
    Output("si-viewer", "alt"),
    Output("si-status", "children"),
    Output("si-status", "color"),
    Output("si-status", "hide", allow_duplicate=True),
    Output("si-json", "children"),
    Output("si-working", "children"),
    Output("si-poll", "disabled", allow_duplicate=True),
    Output("si-working", "display", allow_duplicate=True),
    Output("si-go", "loading", allow_duplicate=True),
    Input("si-poll", "n_intervals"),
    State("si-run", "data"),
    prevent_initial_call=True,
)
def poll(_, run_id):
    """Same seam, same collector as /generative-3d — see lib/build_stream.py."""
    idle = (no_update,) * 10
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
                f"Read the image in {event.get('seconds', 0)}s — "
                f"assembling {event['total']} parts"
            )
        elif phase == "done":
            final = event

    if final is not None:
        manifest = final.get("manifest") or {}
        note = f"{manifest.get('name', 'Untitled')} — {manifest.get('notes', '')}"
        if final.get("notes"):
            note += "  ·  " + "; ".join(final["notes"])
        note += f"  ·  {final.get('part_count', 0)} parts in {final.get('seconds', 0)}s"
        return (
            final.get("data_url") or latest_src,
            f"A sculpture evoking the uploaded image: {manifest.get('name', 'untitled')}",
            note, "indigo", False,
            json.dumps(manifest, indent=2),
            "", True, "none", False,
        )

    if state["done"]:
        return (
            no_update, no_update,
            state["reason"] or "The sculpt did not complete.",
            "yellow", False, no_update,
            "", True, "none", False,
        )

    return (
        latest_src, no_update, no_update, no_update, no_update, no_update,
        progress, no_update, no_update, no_update,
    )


@callback(
    Output("si-status", "children", allow_duplicate=True),
    Output("si-status", "hide", allow_duplicate=True),
    Output("si-status", "color", allow_duplicate=True),
    Input("si-upload", "contents"),
    prevent_initial_call=True,
)
def show_budget(_):
    """What is left, before spending any of it."""
    left = spend.remaining()
    return (
        f"This shared demo has {left.calls_left} calls and "
        f"${left.usd_left:.2f} of estimated budget left this hour.",
        False,
        "gray",
    )
