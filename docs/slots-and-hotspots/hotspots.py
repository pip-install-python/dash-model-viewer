from dash import Input, Output, callback, html
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib.demo_models import ASTRONAUT

component = html.Div(
    [
        dmv.ModelViewer(
            id="sh-viewer",
            src=ASTRONAUT,
            alt="An astronaut with labelled hotspots on the visor and backpack",
            camera_orbit="15deg 80deg 3.5m",
            camera_target="0m 1.1m 0m",
            style={"width": "100%", "height": "420px"},
            children=[
                dmv.Slot(
                    id="sh-visor",
                    slot="hotspot-visor",
                    position="0 1.75 0.35",
                    normal="0 0 1",
                    children=dmc.Badge("Visor", color="indigo", variant="filled"),
                ),
                dmv.Slot(
                    id="sh-pack",
                    slot="hotspot-pack",
                    position="0 1.4 -0.35",
                    normal="0 0 -1",
                    children=dmc.Badge("Life support", color="teal", variant="filled"),
                ),
            ],
        ),
        dmc.Text("Click a badge on the model.", id="sh-readout", size="sm", mt="sm"),
    ]
)


@callback(
    Output("sh-readout", "children"),
    Input("sh-visor", "n_clicks"),
    Input("sh-pack", "n_clicks"),
)
def describe(visor, pack):
    return f"Visor clicked {visor or 0}x · Life support clicked {pack or 0}x"
