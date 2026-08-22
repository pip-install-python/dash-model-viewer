from dash import Input, Output, callback, html
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib.demo_models import ROBOT

component = html.Div(
    [
        dmv.ModelViewer(
            id="ev-camera-viewer",
            src=ROBOT,
            alt="An expressive cartoon robot",
            camera_change_debounce=120,
            style={"width": "100%", "height": "360px"},
        ),
        dmc.Code(
            "Drag the model.",
            id="ev-camera-readout",
            block=True,
            mt="sm",
        ),
    ]
)


@callback(
    Output("ev-camera-readout", "children"),
    Input("ev-camera-viewer", "camera"),
)
def show_camera(camera):
    if not camera:
        return "Drag the model."
    return (
        f"orbit  {camera['orbit']}\n"
        f"target {camera['target']}\n"
        f"fov    {camera['field_of_view']}\n"
        f"source {camera['source']}"
    )
