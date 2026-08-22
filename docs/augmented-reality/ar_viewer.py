from dash import Input, Output, callback, html
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib.demo_models import ASTRONAUT

component = html.Div(
    [
        dmv.ModelViewer(
            id="ar-viewer",
            src=ASTRONAUT,
            alt="An astronaut, placeable in your room with AR",
            ar=True,
            # This is the default. Shown explicitly because the equivalent
            # line in 0.0.1 read "basic_annotations scene-viewer quick-look".
            ar_modes="webxr scene-viewer quick-look",
            ar_scale="auto",
            shadow_intensity=1,
            style={"width": "100%", "height": "400px"},
            children=[
                dmv.Slot(
                    slot="ar-button",
                    children=dmc.Button("View in your space", variant="filled"),
                ),
                dmv.Slot(
                    slot="ar-failure",
                    children=dmc.Alert("AR lost tracking — try more light.",
                                       color="red"),
                ),
            ],
        ),
        dmc.Text(id="ar-readout", size="sm", mt="sm"),
    ]
)


@callback(
    Output("ar-readout", "children"),
    Input("ar-viewer", "ar_status"),
    Input("ar-viewer", "ar_tracking"),
)
def report(status, tracking):
    if not status:
        return "On a phone, tap the button above. On desktop, nothing happens — by design."
    return f"ar_status: {status} · ar_tracking: {tracking or 'n/a'}"
