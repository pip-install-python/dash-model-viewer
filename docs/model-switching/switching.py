from dash import Input, Output, callback, html, no_update
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib.demo_models import ASTRONAUT, ROBOT, SHOE

MODELS = {"Astronaut": ASTRONAUT, "Robot": ROBOT, "Shoe": SHOE}

component = html.Div(
    [
        dmc.Group(
            [
                dmc.SegmentedControl(id="ms-model", data=list(MODELS), value="Shoe"),
                dmc.Select(
                    id="ms-variant",
                    placeholder="Variant",
                    data=[],
                    w=200,
                    clearable=True,
                ),
            ],
            mb="sm",
        ),
        dmv.ModelViewer(
            id="ms-viewer",
            src=SHOE,
            alt="A shoe whose material variants can be switched at runtime",
            camera_controls=True,
            shadow_intensity=1,
            style={"width": "100%", "height": "380px"},
        ),
    ]
)


@callback(Output("ms-viewer", "src"), Input("ms-model", "value"))
def swap_model(name):
    return MODELS[name]


@callback(
    Output("ms-variant", "data"),
    Output("ms-variant", "value"),
    Input("ms-viewer", "model_info"),
)
def list_variants(info):
    """The viewer tells us which variants the file actually contains."""
    variants = (info or {}).get("variants") or []
    return variants, None


@callback(
    Output("ms-viewer", "variant_name"),
    Input("ms-variant", "value"),
    prevent_initial_call=True,
)
def choose_variant(value):
    return value if value else no_update
