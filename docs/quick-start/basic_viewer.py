from dash import html

import dash_model_viewer as dmv
from lib.demo_models import ASTRONAUT

component = html.Div(
    dmv.ModelViewer(
        id="qs-viewer",
        src=ASTRONAUT,
        alt="A 3D model of an astronaut in a white spacesuit",
        style={"width": "100%", "height": "420px"},
    )
)
