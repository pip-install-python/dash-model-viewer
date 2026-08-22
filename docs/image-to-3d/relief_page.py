import base64
import json
from pathlib import Path

from dash import Input, Output, callback, dcc, html, no_update
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib import relief

VIEWER_ATTRS = {
    "environment-image": "neutral",
    "exposure": "1.15",
    "shadow-softness": "0.6",
}

# The page opens on a relief of this site's own logo, carved with DEFAULT
# parameters and zero API calls — so the geometry half is demonstrably working
# before anyone spends anything, and the page is never an empty box.
_SAMPLE = Path("assets/logo.png")
_sample_glb, _sample_stats = relief.carve(
    _SAMPLE.read_bytes(),
    {"depth_profile": "punchy", "depth_scale": 0.16, "invert": False,
     "background": "alpha", "metallic": 0.15, "roughness": 0.55},
)

component = html.Div(
    [
        dcc.Upload(
            id="i3-upload",
            children=dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Text("Drop a PNG or JPEG here", fw=600),
                        dmc.Text("or click to choose · 6 MB max", size="xs", c="dimmed"),
                    ],
                    gap=2,
                    align="center",
                ),
                withBorder=True,
                radius="md",
                p="lg",
                style={"borderStyle": "dashed", "cursor": "pointer"},
            ),
            multiple=False,
            accept="image/*",
        ),
        dmc.Space(h="sm"),
        # There is no button here — the upload itself is the trigger — so the
        # busy state is the ONLY signal that anything is happening. A vision
        # call plus a 29k-triangle carve is several seconds of nothing.
        dmc.Box(
            pos="relative",
            children=[
                dmc.LoadingOverlay(
                    id="i3-busy",
                    visible=False,
                    zIndex=10,
                    overlayProps={"radius": "md", "blur": 2},
                    loaderProps={"type": "bars", "color": "indigo"},
                ),
                dmv.ModelViewer(
                    id="i3-viewer",
                    src=relief.to_data_url(_sample_glb),
                    alt="A bas-relief carved from the dash-model-viewer logo",
                    camera_controls=True,
                    camera_orbit="20deg 72deg 0.6m",
                    shadow_intensity=1,
                    interpolation_decay=90,
                    attributes=VIEWER_ATTRS,
                    style={"width": "100%", "height": "430px"},
                ),
            ],
        ),
        dmc.Text(
            # Measured: ~8.5s for the vision call, ~0.2s for the carve.
        "Reading the image and carving — about 10 seconds.",
            id="i3-working", size="sm", c="dimmed", mt="xs", display="none",
        ),
        dmc.Alert(id="i3-status", mt="sm", color="indigo", hide=True),
        dmc.Spoiler(
            id="i3-spoiler",
            showLabel="Show the carving parameters",
            hideLabel="Hide",
            maxHeight=0,
            children=dmc.Code(id="i3-json", block=True),
            mt="xs",
        ),
    ]
)


@callback(
    Output("i3-viewer", "src"),
    Output("i3-viewer", "alt"),
    Output("i3-status", "children"),
    Output("i3-status", "color"),
    Output("i3-status", "hide"),
    Output("i3-json", "children"),
    Input("i3-upload", "contents"),
    running=[
        (Output("i3-busy", "visible"), True, False),
        (Output("i3-upload", "disabled"), True, False),
        (Output("i3-working", "display"), "block", "none"),
    ],
    prevent_initial_call=True,
)
def carve_upload(contents):
    if not contents:
        return (no_update,) * 6

    # dcc.Upload hands back "data:<media-type>;base64,<payload>".
    try:
        header, payload = contents.split(",", 1)
        media_type = header.split(";")[0].removeprefix("data:") or "image/png"
        raw = base64.b64decode(payload)
    except Exception:
        return no_update, no_update, "That upload could not be decoded.", "red", False, no_update

    result = relief.relief_from_image(raw, media_type)
    if not result.ok:
        return no_update, no_update, result.reason, "yellow", False, no_update

    note = f"{result.title} — {result.params.get('notes', '')}"
    if result.notes:
        note += "  ·  " + "; ".join(result.notes)
    s = result.stats
    note += (f"  ·  {s['grid']} grid, {s['triangles']:,} triangles, "
             f"{s['glb_bytes'] / 1024:.0f} KB")

    return (
        result.data_url,
        result.alt,
        note,
        "indigo",
        False,
        json.dumps(result.params, indent=2),
    )
