import json
import threading
from datetime import date

from dash import Input, Output, State, callback, dcc, html, no_update
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib import (build_stream, manifest, model_picker, poll_guard, sculptor,
                 spend, texture, uploads)

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
        # The bounded timer and its liveness store. Capped and stale-guarded
        # in one place — see lib/poll_guard.py for the 500-loop it ends.
        *poll_guard.components("si"),
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
                dmc.Text("Texture", size="xs", c="dimmed"),
                dmc.SegmentedControl(
                    id="si-texture",
                    value="off",
                    size="xs",
                    data=[
                        {"label": "Off", "value": "off"},
                        {"label": "Preview", "value": "preview"},
                        {"label": "Include", "value": "include"},
                    ],
                ),
                dmc.Text(id="si-texture-note", size="xs", c="dimmed"),
            ],
            gap="xs", mt="sm", align="center",
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
    Output("si-poll", "n_intervals"),
    Output("si-alive", "data"),
    Input("si-go", "n_clicks"),
    State("si-image", "data"),
    State("si-hint", "value"),
    State("si-model", "value"),
    prevent_initial_call=True,
)
def start(_, image, hint, model):
    if not image:
        return (no_update,) * 7
    run_id = build_stream.new_run()
    threading.Thread(
        target=sculptor.sculpt_image_streaming,
        args=(run_id, image, hint or ""),
        kwargs={"model": model or sculptor.MODEL},
        daemon=True,
    ).start()
    # n_intervals back to 0 re-arms the capped Interval (the gate is
    # `n_intervals >= max_intervals`, re-evaluated on update), so the ceiling
    # bounds THIS build rather than the tab's whole lifetime.
    return run_id, False, True, "block", True, 0, poll_guard.tick_value(0)


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
    Output("si-alive", "data", allow_duplicate=True),
    Input("si-poll", "n_intervals"),
    State("si-run", "data"),
    State("si-model", "value"),
    State("si-hint", "value"),
    prevent_initial_call=True,
)
def poll(tick, run_id, model, hint):
    """Same seam, same collector as /generative-3d — see lib/build_stream.py.

    EVERY return path advances `si-alive`, including the ones that report no
    progress: it records that the SERVER ANSWERED, not that something
    changed. A store advanced only when a part arrives would trip the stale
    guard during any build whose first model call runs long.
    """
    alive = poll_guard.tick_value(tick)
    idle = (no_update,) * 13 + (alive,)
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
            }), False, False, alive,
        )

    if state["done"]:
        return (
            no_update, no_update,
            state["reason"] or "The sculpt did not complete.",
            "yellow", False, no_update,
            "", True, "none", False,
            no_update, no_update, no_update, alive,
        )

    return (
        latest_src, no_update, no_update, no_update, no_update, no_update,
        progress, no_update, no_update, no_update,
        no_update, no_update, no_update, alive,
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
poll_guard.register("si", "si-status", resets=[
    ("si-working", "display", "none"),
    ("si-go", "loading", False),
])


#: What each switch position means, in one place, so the note under the
#: control, the button label and the download cannot disagree about it.
TEXTURE_MODES = ("off", "preview", "include")


def texture_png(image_contents):
    """The uploaded image, decoded and downscaled for baking — or None.

    Reuses `lib/uploads.py`'s rules rather than a second set: this is the same
    upload the vision model read, and two answers to "is this acceptable" is
    how one page silently gets a different cap from the other.
    """
    raw, _media_type, _message = uploads.decode_image(
        image_contents, max_bytes=MAX_IMAGE_BYTES
    )
    if raw is None:
        return None
    try:
        return texture.prepare(raw)
    except Exception:                                     # noqa: BLE001
        # Pillow raises a family of its own errors for a truncated or hostile
        # raster. A texture that cannot be prepared must not take the page
        # down — the sculpture is still there to look at untextured.
        return None


def _note(mode, has_image, has_manifest):
    if mode == "off":
        return "The sculpture keeps its generated colours."
    if not has_manifest:
        return "Sculpt something first."
    if not has_image:
        return "Upload an image to drape it."
    if mode == "preview":
        return "Draped on screen only — the .glb downloads untextured."
    return "Draped, and baked into the .glb you download."


@callback(
    Output("si-viewer", "src", allow_duplicate=True),
    Output("si-texture-note", "children"),
    Output("si-save-glb", "children"),
    Input("si-texture", "value"),
    Input("si-manifest", "data"),
    State("si-image", "data"),
    prevent_initial_call=True,
)
def retexture(mode, stored, image):
    """Re-render the stored sculpture at the chosen texture setting.

    NO MODEL IS CALLED. The manifest is already in hand and `lib/glb.py` is
    deterministic, so switching costs a rebuild and nothing else — which is the
    reason the switch can exist at all, and the reason it is a switch rather
    than a checkbox you set before paying for a sculpt.

    `si-manifest` is an Input, not a State, so a fresh sculpt comes out at
    whatever setting is currently chosen instead of silently reverting to Off.
    """
    mode = mode if mode in TEXTURE_MODES else "off"
    label = "Download .glb (untextured)" if mode == "preview" else "Download .glb"
    if not stored:
        return no_update, _note(mode, bool(image), False), label

    png = texture_png(image) if mode in ("preview", "include") else None
    try:
        data, _notes, _used = manifest.render(stored, texture_png=png)
    except (manifest.ManifestError, ValueError):
        return no_update, _note(mode, bool(image), True), label
    return (sculptor.to_data_url(data),
            _note(mode, png is not None, True),
            label)


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
    State("si-texture", "value"),
    State("si-image", "data"),
    prevent_initial_call=True,
)
def save_glb(_clicks, stored, mode, image):
    """Rebuilt from the stored manifest on demand, not carried as bytes.

    `lib/glb.py` is deterministic, so this is the same file the viewer is
    showing — and it keeps a megabyte of binary out of the browser's store.
    Nothing is written to disk at any point.

    ONLY `include` BAKES. Under `preview` the download is deliberately the
    plain sculpture, and the button says so, because a file that quietly
    differs from what is on screen is worse than one that plainly does not
    match. `off` and `preview` therefore produce the same bytes as before the
    feature existed.

    Two callbacks rather than one dispatching on `ctx.triggered_id`: a callback
    that reads the context cannot be called from a test, and these two are
    worth testing.
    """
    if not stored:
        return no_update
    png = texture_png(image) if mode == "include" else None
    try:
        m = manifest.validate(stored)
        data, _notes, _used = manifest.render(m, texture_png=png)
    except (manifest.ManifestError, ValueError):
        return no_update
    stem = manifest.filename(m, "glb")
    if png is not None:
        stem = stem[:-4] + "-textured.glb"
    return dcc.send_bytes(data, stem)
