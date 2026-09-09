from dash import Input, Output, callback, html
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib.demo_models import ASTRONAUT

component = html.Div(
    [
        dmv.ModelViewer(
            id="ev-pick-viewer",
            src=ASTRONAUT,
            alt="An astronaut model; clicking its surface reports the point under the cursor",
            camera_controls=True,
            # Without this the click listener returns immediately and
            # `scene_point` never updates.
            pick_on_click=True,
            style={"width": "100%", "height": "320px"},
        ),
        dmc.Text("Click the astronaut.", id="ev-pick-status", size="sm", mt="sm"),
        dmc.Code(id="ev-pick-readout", block=True, mt="xs"),
    ]
)


@callback(
    Output("ev-pick-status", "children"),
    Output("ev-pick-readout", "children"),
    Input("ev-pick-viewer", "scene_point"),
)
def show_point(point):
    # `scene_point` is None both before the first click and whenever a click
    # misses the mesh — which is the common case near the silhouette, so the
    # miss is a real state to render rather than an error to hide.
    if not point:
        return "Click the astronaut.", "No point yet — a click that misses the mesh reports None."
    uv = point.get("uv")
    return (
        "Picked.",
        f"position {point['position']}\n"
        f"normal   {point['normal']}\n"
        f"uv       {f'{uv[0]:.3f}, {uv[1]:.3f}' if uv else '(none — model has no UVs)'}",
    )
