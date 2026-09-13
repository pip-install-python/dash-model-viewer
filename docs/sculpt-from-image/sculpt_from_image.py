import json
import threading
from datetime import date

from dash import Input, Output, State, callback, dcc, html, no_update
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib import build_stream, manifest, model_picker, sculptor, spend, uploads

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
        dcc.Store(id="si-manifest"),
        dcc.Download(id="si-dl-json"),
        dcc.Download(id="si-dl-glb"),
        dcc.Interval(id="si-poll", interval=700, disabled=True),
        dmc.Group(
            model_picker.components("si", sculptor.MODEL, w=260),
            mb="xs",
        ),
        dmc.Text(id="si-model-status", size="xs", c="dimmed"),
        dmc.Text(id="si-estimate", size="xs", c="dimmed", mb="xs"),
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
        dmc.Group(
            [
                dmc.Button("Save the manifest", id="si-save-json",
                           variant="light", size="xs", disabled=True),
                dmc.Button("Download .glb", id="si-save-glb",
                           variant="light", size="xs", disabled=True),
            ],
            gap="xs", mt="xs",
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
    State("si-model", "value"),
    prevent_initial_call=True,
)
def start(_, image, hint, model):
    if not image:
        return no_update, no_update, no_update, no_update, no_update
    run_id = build_stream.new_run()
    threading.Thread(
        target=sculptor.sculpt_image_streaming,
        args=(run_id, image, hint or ""),
        kwargs={"model": model or sculptor.MODEL},
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
    Output("si-manifest", "data"),
    Output("si-save-json", "disabled"),
    Output("si-save-glb", "disabled"),
    Input("si-poll", "n_intervals"),
    State("si-run", "data"),
    State("si-model", "value"),
    State("si-hint", "value"),
    prevent_initial_call=True,
)
def poll(_, run_id, model, hint):
    """Same seam, same collector as /generative-3d — see lib/build_stream.py."""
    idle = (no_update,) * 13
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
        # NOT named `manifest` — see the note in /generative-3d's poll.
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
            f"A sculpture evoking the uploaded image: {scene.get('name', 'untitled')}",
            note, "indigo", False,
            json.dumps(scene, indent=2),
            "", True, "none", False,
            manifest.from_scene(scene, {
                "prompt": hint or "(no hint — the image alone)",
                "model": model,
                "usd": final.get("usd", 0.0),
                "generated": date.today().isoformat(),
            }), False, False,
        )

    if state["done"]:
        return (
            no_update, no_update,
            state["reason"] or "The sculpt did not complete.",
            "yellow", False, no_update,
            "", True, "none", False,
            no_update, no_update, no_update,
        )

    return (
        latest_src, no_update, no_update, no_update, no_update, no_update,
        progress, no_update, no_update, no_update,
        no_update, no_update, no_update,
    )


@callback(
    Output("si-estimate", "children"),
    Input("si-model", "value"),
)
def show_estimate(model):
    """Priced BEFORE the button. A vision call is not free and the visitor is
    spending the owner's credits, so the number belongs where the decision is."""
    return spend.estimate_line(model or sculptor.MODEL, sculptor.MAX_TOKENS)


model_picker.register("si", action_ids=["si-go"])


@callback(
    Output("si-dl-json", "data"),
    Input("si-save-json", "n_clicks"),
    State("si-manifest", "data"),
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
    Output("si-dl-glb", "data"),
    Input("si-save-glb", "n_clicks"),
    State("si-manifest", "data"),
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
