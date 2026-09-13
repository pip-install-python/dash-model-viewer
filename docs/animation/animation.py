from dash import Input, Output, State, callback, html, no_update
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib.demo_models import ROBOT

#: Lighting that makes a moving figure readable. A matte grey character against
#: a flat background reads as a bug report; this reads as a character.
BASE_ATTRS = {
    "environment-image": "neutral",
    "shadow-softness": "0.6",
}

#: Milliseconds of blend when switching clips. 0 is a hard cut and is the
#: default most people expect to be wrong — see the page.
DEFAULT_CROSSFADE = 300

component = html.Div(
    [
        dmc.Group(
            [
                dmc.Select(
                    id="an-name",
                    label="Animation",
                    # Filled from the model itself, not hardcoded — see below.
                    data=[],
                    w=220,
                    allowDeselect=False,
                ),
                dmc.NumberInput(
                    id="an-crossfade",
                    label="Crossfade (ms)",
                    value=DEFAULT_CROSSFADE,
                    min=0,
                    max=2000,
                    step=100,
                    w=150,
                ),
                dmc.Switch(
                    id="an-playing",
                    label="Playing",
                    checked=True,
                    mt="xl",
                ),
            ],
            mb="sm",
            align="flex-end",
        ),
        dmv.ModelViewer(
            id="an-viewer",
            src=ROBOT,
            alt="An expressive cartoon robot playing one of its built-in animation clips",
            camera_controls=True,
            shadow_intensity=1,
            # `autoplay` starts the first clip. Without it the model loads in
            # its bind pose and looks broken rather than idle.
            attributes={**BASE_ATTRS, "autoplay": ""},
            style={"width": "100%", "height": "460px"},
        ),
        dmc.Text(id="an-status", size="sm", c="dimmed", mt="xs"),
    ]
)


@callback(
    Output("an-name", "data"),
    Output("an-name", "value"),
    Output("an-status", "children"),
    Input("an-viewer", "model_info"),
    State("an-name", "value"),
)
def list_animations(info, current):
    """The viewer reports the clips; the page never hardcodes them.

    `model_info["animations"]` is the same prop /model-switching uses for
    material variants, and it arrives with the `load` event. So this picker
    works for ANY model the src is pointed at — which is the point, and is
    what a hardcoded list of Robot Expressive's fourteen clips would have
    quietly broken the moment somebody changed the model.
    """
    if not info:
        return [], None, "Loading the model…"
    clips = info.get("animations") or []
    if not clips:
        return [], None, "This model carries no animation clips."
    chosen = current if current in clips else clips[0]
    return clips, chosen, f"{len(clips)} clips: {', '.join(clips)}"


@callback(
    Output("an-viewer", "attributes"),
    Input("an-name", "value"),
    Input("an-crossfade", "value"),
    Input("an-playing", "checked"),
)
def drive_animation(name, crossfade, playing):
    """Everything here is an ATTRIBUTE, not a method call.

    1.0.0 ships no imperative surface — no `play()`, no `pause()` — so the
    whole of this page runs through the `attributes` escape hatch. That is the
    honest demonstration of what the hatch is for.

    `paused` is a boolean attribute: its PRESENCE pauses. So resuming means
    leaving the key out of the dict entirely rather than setting it false, and
    the shim removes any attribute that disappears between renders.
    """
    if not name:
        return no_update
    attrs = {
        **BASE_ATTRS,
        "autoplay": "",
        "animation-name": name,
        "animation-crossfade-duration": str(crossfade or 0),
    }
    if not playing:
        attrs["paused"] = ""
    return attrs
