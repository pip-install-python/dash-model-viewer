from dash import Input, Output, State, callback, html
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib.demo_models import ASTRONAUT, MOON_HDR

#: Always on, so the model is lit and the ground reads as ground.
BASE = {"environment-image": "neutral", "shadow-softness": "0.6"}

SCALES = {"1 1 1": "actual size", "0.5 0.5 0.5": "half", "2 2 2": "double"}


def build_attrs(no_pan, no_tap, no_prompt, scale, skybox, skybox_height,
                loading, reveal):
    """The attribute dict, from the controls. Pure, so it can be tested."""
    attrs = dict(BASE)
    attrs["scale"] = scale
    attrs["loading"] = loading
    attrs["reveal"] = reveal

    # Boolean attributes: present means on. OMITTED when off, never "false" —
    # "false" is a present value and would leave them on. See the page.
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
    return attrs


def viewer(attrs):
    return dmv.ModelViewer(
        id="at-viewer",
        src=ASTRONAUT,
        alt="An astronaut used to demonstrate model-viewer attributes that have no named prop",
        camera_controls=True,
        shadow_intensity=1,
        attributes=attrs,
        style={"width": "100%", "height": "460px"},
    )


CONTROLS = dmc.Stack(
    gap="sm",
    children=[
        dmc.Text("What the user may do", size="xs", fw=700),
        dmc.Switch(id="at-pan", label="disable-pan", checked=False),
        dmc.Switch(id="at-tap", label="disable-tap", checked=False),
        dmc.Switch(id="at-prompt", label="interaction-prompt: none", checked=False),
        dmc.Divider(),
        dmc.Text("The scene", size="xs", fw=700),
        dmc.Select(
            id="at-scale", label="scale",
            data=[{"value": k, "label": f"{k} — {v}"} for k, v in SCALES.items()],
            value="1 1 1", allowDeselect=False,
        ),
        dmc.Switch(id="at-skybox", label="skybox-image", checked=False),
        dmc.NumberInput(
            id="at-skybox-height", label="skybox-height (m)",
            value=0, min=0, max=10, step=1,
        ),
        dmc.Divider(),
        dmc.Text("When it loads", size="xs", fw=700),
        dmc.Select(
            id="at-loading", label="loading",
            data=["auto", "lazy", "eager"], value="auto", allowDeselect=False,
        ),
        dmc.Select(
            id="at-reveal", label="reveal",
            data=["auto", "interaction"], value="auto", allowDeselect=False,
        ),
        dmc.Button(
            "Reload the model",
            id="at-reload",
            variant="light",
            mt="xs",
        ),
        dmc.Text(
            "loading and reveal only act while a model is loading. "
            "Press this to see them.",
            size="xs", c="dimmed",
        ),
    ],
)

component = html.Div(
    [
        dmc.Grid(
            gutter="md",
            children=[
                dmc.GridCol(CONTROLS, span={"base": 12, "md": 4}),
                dmc.GridCol(
                    # The viewer is HERE, in the initial layout, and updates in
                    # place. An earlier version rebuilt it from a callback on
                    # every control, which reloaded the model and reset the
                    # camera each time — so `disable-pan` and `disable-tap` did
                    # work and were impossible to SEE, and the remount reset the
                    # idle timer so `interaction-prompt: none` made the prompt
                    # reappear. The reload is now an explicit button.
                    html.Div(id="at-mount", children=viewer(build_attrs(
                        False, False, False, "1 1 1", False, 0, "auto", "auto"
                    ))),
                    span={"base": 12, "md": 8},
                ),
            ],
        ),
        dmc.Code(id="at-readout", block=True, mt="sm"),
    ]
)

_CONTROL_STATE = (
    Input("at-pan", "checked"),
    Input("at-tap", "checked"),
    Input("at-prompt", "checked"),
    Input("at-scale", "value"),
    Input("at-skybox", "checked"),
    Input("at-skybox-height", "value"),
    Input("at-loading", "value"),
    Input("at-reveal", "value"),
)


@callback(
    Output("at-viewer", "attributes"),
    Output("at-readout", "children"),
    *_CONTROL_STATE,
)
def apply_attributes(*values):
    """Update the live element IN PLACE — no reload, no camera reset.

    That is what makes `disable-pan`, `disable-tap` and `interaction-prompt`
    observable: you can toggle one and immediately try the gesture against the
    same view. The shim diffs the dict and removes whatever disappeared.
    """
    attrs = build_attrs(*values)
    rendered = "\n".join(f'{k}="{v}"' if v else k for k, v in sorted(attrs.items()))
    return attrs, rendered


@callback(
    Output("at-mount", "children"),
    Input("at-reload", "n_clicks"),
    *[State(dep.component_id, dep.component_property) for dep in _CONTROL_STATE],
    prevent_initial_call=True,
)
def reload_model(_clicks, *values):
    """Remount, and ONLY on request.

    `loading` and `reveal` do nothing to a model that has already loaded, so
    they need a fresh mount to be observable at all. Doing that on every
    control change — as this page first did — obscured every other attribute
    on it. A button makes the reload deliberate and leaves the rest alone.
    """
    return viewer(build_attrs(*values))
