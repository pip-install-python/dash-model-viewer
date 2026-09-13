from dash import Input, Output, callback, html
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib.demo_models import ASTRONAUT, MOON_HDR

#: Always on, so the model is lit and the ground reads as ground.
BASE = {"environment-image": "neutral", "shadow-softness": "0.6"}

SCALES = {"1 1 1": "actual size", "0.5 0.5 0.5": "half", "2 2 2": "double"}

component = html.Div(
    [
        dmc.Grid(
            gutter="md",
            children=[
                dmc.GridCol(
                    dmc.Stack(
                        gap="sm",
                        children=[
                            dmc.Text("What the user may do", size="xs", fw=700),
                            dmc.Switch(id="at-pan", label="disable-pan", checked=False),
                            dmc.Switch(id="at-tap", label="disable-tap", checked=False),
                            dmc.Switch(
                                id="at-prompt",
                                label="interaction-prompt: none",
                                checked=False,
                            ),
                            dmc.Divider(),
                            dmc.Text("The scene", size="xs", fw=700),
                            dmc.Select(
                                id="at-scale",
                                label="scale",
                                data=[{"value": k, "label": f"{k} — {v}"}
                                      for k, v in SCALES.items()],
                                value="1 1 1",
                                allowDeselect=False,
                            ),
                            dmc.Switch(id="at-skybox", label="skybox-image", checked=False),
                            dmc.NumberInput(
                                id="at-skybox-height",
                                label="skybox-height (m)",
                                value=0,
                                min=0,
                                max=10,
                                step=1,
                            ),
                            dmc.Divider(),
                            dmc.Text("When it loads", size="xs", fw=700),
                            dmc.Select(
                                id="at-loading",
                                label="loading",
                                data=["auto", "lazy", "eager"],
                                value="auto",
                                allowDeselect=False,
                            ),
                            dmc.Select(
                                id="at-reveal",
                                label="reveal",
                                data=["auto", "interaction"],
                                value="auto",
                                allowDeselect=False,
                            ),
                        ],
                    ),
                    span={"base": 12, "md": 4},
                ),
                dmc.GridCol(
                    html.Div(id="at-mount"),
                    span={"base": 12, "md": 8},
                ),
            ],
        ),
        dmc.Code(id="at-readout", block=True, mt="sm"),
    ]
)


@callback(
    Output("at-mount", "children"),
    Output("at-readout", "children"),
    Input("at-pan", "checked"),
    Input("at-tap", "checked"),
    Input("at-prompt", "checked"),
    Input("at-scale", "value"),
    Input("at-skybox", "checked"),
    Input("at-skybox-height", "value"),
    Input("at-loading", "value"),
    Input("at-reveal", "value"),
)
def rebuild(no_pan, no_tap, no_prompt, scale, skybox, skybox_height, loading, reveal):
    """Rebuild the whole viewer, on purpose.

    Most pages on this site change a prop and let the element update in place.
    This one REMOUNTS, because two of the attributes it demonstrates —
    `loading` and `reveal` — only do anything while a model is being loaded.
    Toggling them on a viewer that has already loaded shows nothing at all, so
    a page that updated in place would look broken for exactly the two
    settings hardest to believe.

    The id stays the same, so anything keyed on it keeps working; only the
    element is new.
    """
    attrs = dict(BASE)
    attrs["scale"] = scale
    attrs["loading"] = loading
    attrs["reveal"] = reveal

    # Boolean attributes: present means on. Omitted, not "false" — see the page.
    if no_pan:
        attrs["disable-pan"] = ""
    if no_tap:
        attrs["disable-tap"] = ""
    if no_prompt:
        attrs["interaction-prompt"] = "none"
    if skybox:
        attrs["skybox-image"] = MOON_HDR
        # Only meaningful with a skybox; sending it alone does nothing, which
        # is why it is nested rather than listed beside the others.
        if skybox_height:
            attrs["skybox-height"] = f"{skybox_height}m"

    viewer = dmv.ModelViewer(
        id="at-viewer",
        src=ASTRONAUT,
        alt="An astronaut used to demonstrate model-viewer attributes that have no named prop",
        camera_controls=True,
        shadow_intensity=1,
        attributes=attrs,
        style={"width": "100%", "height": "460px"},
    )
    rendered = "\n".join(f'{k}="{v}"' if v else k for k, v in sorted(attrs.items()))
    return viewer, rendered
