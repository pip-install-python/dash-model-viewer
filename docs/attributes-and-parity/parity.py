from dash import Input, Output, callback, html
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib.demo_models import CANDLE_GLASS, MOON_HDR

# Not one of these is a named prop on ModelViewer. They work anyway.
PRESETS = {
    "Studio": {"environment-image": "neutral", "exposure": "1"},
    "Moonlight": {"environment-image": MOON_HDR, "exposure": "1.4"},
    "Spinning": {"auto-rotate": "", "auto-rotate-delay": "0", "rotation-per-second": "20deg"},
    "Tilted": {"orientation": "0deg 0deg 20deg", "exposure": "1.1"},
}

component = html.Div(
    [
        dmc.SegmentedControl(
            id="ap-preset",
            data=list(PRESETS),
            value="Studio",
            fullWidth=True,
            mb="sm",
        ),
        dmv.ModelViewer(
            id="ap-viewer",
            # Glass, not the astronaut: this page is about lighting attributes,
            # and physically-based transparency and refraction respond to
            # `environment-image` and `exposure` far more visibly than a matte
            # spacesuit does. No camera props here — model-viewer auto-frames,
            # so swapping the model needs no hand-tuned orbit.
            src=CANDLE_GLASS,
            alt="A glass candle holder re-lit by attributes the package has no named prop for",
            shadow_intensity=1,
            style={"width": "100%", "height": "380px"},
        ),
        dmc.Code(id="ap-readout", block=True, mt="sm"),
    ]
)


@callback(
    Output("ap-viewer", "attributes"),
    Output("ap-readout", "children"),
    Input("ap-preset", "value"),
)
def apply_preset(name):
    attrs = PRESETS[name]
    rendered = "\n".join(f'{k}="{v}"' for k, v in attrs.items())
    return attrs, rendered
