from dash import Input, Output, callback, html
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib.demo_models import ODD_SHAPE

component = html.Div(
    [
        dmv.ModelViewer(
            id="ev-load-viewer",
            src=ODD_SHAPE,
            alt="A labelled irregular solid used to show measured dimensions",
            camera_controls=True,
            style={"width": "100%", "height": "320px"},
        ),
        dmc.Progress(id="ev-load-progress", value=0, mt="sm", animated=True),
        dmc.Text(id="ev-load-status", size="sm", mt="xs"),
        dmc.Code(id="ev-load-dims", block=True, mt="xs"),
    ]
)


@callback(
    Output("ev-load-progress", "value"),
    Output("ev-load-status", "children"),
    Input("ev-load-viewer", "model_state"),
)
def show_progress(state):
    if not state:
        return 0, "Waiting for the model…"
    pct = round((state.get("progress") or 0) * 100)
    return pct, f"{state['status']} — {pct}%"


@callback(
    Output("ev-load-dims", "children"),
    Input("ev-load-viewer", "model_info"),
)
def show_dimensions(info):
    if not info or not info.get("dimensions"):
        return "Dimensions arrive with the `load` event."
    d = info["dimensions"]
    return (
        f"width  {d['x']:.3f} m\n"
        f"height {d['y']:.3f} m\n"
        f"depth  {d['z']:.3f} m\n"
        f"variants   {info['variants'] or '(none)'}\n"
        f"animations {info['animations'] or '(none)'}"
    )
