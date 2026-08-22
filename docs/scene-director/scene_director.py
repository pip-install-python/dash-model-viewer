import json

from dash import ALL, Input, Output, State, callback, ctx, html, no_update
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib import scene_director
from lib.demo_models import SHOE

PROMPTS = [
    "dramatic low three-quarter angle, focus on the sole",
    "clean straight-on product shot for a shop listing",
    "top-down, tight, soft shadow",
    "slowly rotating hero shot, warm and premium",
]

component = html.Div(
    [
        dmc.Group(
            [
                dmc.TextInput(
                    id="sd-prompt",
                    placeholder="Describe the shot you want…",
                    value=PROMPTS[0],
                    style={"flex": 1},
                ),
                dmc.Button("Direct", id="sd-go", variant="filled"),
            ],
            mb="xs",
            align="flex-end",
        ),
        dmc.Group(
            [
                dmc.Badge(p, id={"type": "sd-preset", "i": i},
                          variant="light", style={"cursor": "pointer"})
                for i, p in enumerate(PROMPTS)
            ],
            gap="xs",
            mb="sm",
        ),
        dmc.Box(
            pos="relative",
            children=[
                dmc.LoadingOverlay(
                    id="sd-busy",
                    visible=False,
                    zIndex=10,
                    overlayProps={"radius": "md", "blur": 2},
                    loaderProps={"type": "bars", "color": "indigo"},
                ),
                dmv.ModelViewer(
                    id="sd-viewer",
                    src=SHOE,
                    alt="A shoe, restaged from a natural-language description",
                    camera_controls=True,
                    interpolation_decay=90,
                    shadow_intensity=1,
                    style={"width": "100%", "height": "400px"},
                ),
            ],
        ),
        dmc.Text(
            # Measured: ~4s (effort="low", short reasoning).
        "Directing — about 5 seconds.",
            id="sd-working", size="sm", c="dimmed", mt="xs", display="none",
        ),
        dmc.Alert(id="sd-status", mt="sm", color="indigo", hide=True),
        dmc.Code(id="sd-json", block=True, mt="xs"),
    ]
)


@callback(
    Output("sd-prompt", "value"),
    Input({"type": "sd-preset", "i": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def use_preset(clicks):
    if not any(clicks or []):
        return no_update
    return PROMPTS[ctx.triggered_id["i"]]


@callback(
    Output("sd-viewer", "camera_orbit"),
    Output("sd-viewer", "camera_target"),
    Output("sd-viewer", "field_of_view"),
    Output("sd-viewer", "tone_mapping"),
    Output("sd-viewer", "shadow_intensity"),
    Output("sd-viewer", "variant_name"),
    Output("sd-viewer", "attributes"),
    Output("sd-status", "children"),
    Output("sd-status", "color"),
    Output("sd-status", "hide"),
    Output("sd-json", "children"),
    Input("sd-go", "n_clicks"),
    State("sd-prompt", "value"),
    # The grounding. `model_info` is what the viewer measured; `camera` is where
    # the user left it. Both are State — this runs on the button, not on every
    # camera nudge.
    State("sd-viewer", "model_info"),
    State("sd-viewer", "camera"),
    running=[
        (Output("sd-busy", "visible"), True, False),
        (Output("sd-go", "loading"), True, False),
        (Output("sd-prompt", "disabled"), True, False),
        (Output("sd-working", "display"), "block", "none"),
    ],
    prevent_initial_call=True,
)
def direct(_, prompt, model_info, camera):
    result = scene_director.generate(prompt, model_info=model_info, camera=camera)

    if not result.ok:
        return (*(no_update,) * 7, result.reason, "yellow", False, no_update)

    p = result.props
    note = result.rationale
    if result.adjustments:
        note += "  —  " + "; ".join(result.adjustments)

    return (
        p.get("camera_orbit", no_update),
        p.get("camera_target", no_update),
        p.get("field_of_view", no_update),
        p.get("tone_mapping", no_update),
        p.get("shadow_intensity", no_update),
        p.get("variant_name"),
        p.get("attributes", {}),
        note,
        "indigo",
        False,
        json.dumps(p, indent=2),
    )
