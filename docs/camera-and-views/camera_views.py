from dash import ALL, Input, Output, callback, ctx, html
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib.demo_models import ASTRONAUT

# Each preset is one camera pose. Clicking its hotspot flies the camera there.
VIEWS = {
    "Helmet": {"orbit": "0deg 75deg 1.2m", "target": "0m 1.7m 0m", "fov": "30deg"},
    "Torso": {"orbit": "-30deg 85deg 2m", "target": "0m 1.1m 0m", "fov": "40deg"},
    "Boots": {"orbit": "45deg 100deg 1.6m", "target": "0m 0.2m 0m", "fov": "35deg"},
    "Full": {"orbit": "0deg 80deg 4m", "target": "0m 1m 0m", "fov": "45deg"},
}

component = html.Div(
    [
        dmv.ModelViewer(
            id="cv-viewer",
            src=ASTRONAUT,
            alt="An astronaut, with camera presets for the helmet, torso and boots",
            camera_orbit="0deg 80deg 4m",
            camera_target="0m 1m 0m",
            interpolation_decay=120,
            style={"width": "100%", "height": "420px"},
        ),
        dmc.Group(
            [
                dmc.Button(name, id={"type": "cv-view", "name": name},
                           size="xs", variant="light")
                for name in VIEWS
            ],
            mt="sm",
        ),
    ]
)


@callback(
    Output("cv-viewer", "camera_orbit"),
    Output("cv-viewer", "camera_target"),
    Output("cv-viewer", "field_of_view"),
    Input({"type": "cv-view", "name": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def fly_to(_):
    view = VIEWS[ctx.triggered_id["name"]]
    return view["orbit"], view["target"], view["fov"]
