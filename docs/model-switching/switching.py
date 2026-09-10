from dash import Input, Output, callback, html
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib.demo_models import GLAM_SOFA, MODELS_WITH_VARIANTS

MODELS = MODELS_WITH_VARIANTS

component = html.Div(
    [
        dmc.Group(
            [
                dmc.SegmentedControl(id="ms-model", data=list(MODELS), value="Sofa"),
                dmc.Select(
                    id="ms-variant",
                    placeholder="Variant",
                    data=[],
                    w=220,
                    clearable=True,
                ),
            ],
            mb="sm",
        ),
        dmv.ModelViewer(
            id="ms-viewer",
            src=GLAM_SOFA,
            alt="A velvet sofa whose material variants can be switched at runtime",
            camera_controls=True,
            shadow_intensity=1,
            style={"width": "100%", "height": "380px"},
        ),
        dmc.Text(id="ms-status", size="sm", c="dimmed", mt="xs"),
    ]
)


@callback(Output("ms-viewer", "src"), Input("ms-model", "value"))
def swap_model(name):
    return MODELS[name]


@callback(
    Output("ms-variant", "data"),
    Output("ms-variant", "value"),
    Output("ms-variant", "disabled"),
    Output("ms-status", "children"),
    Input("ms-viewer", "model_info"),
)
def list_variants(info):
    """The viewer tells us which variants the file actually contains.

    The empty case is rendered as a visible, disabled state rather than an
    enabled dropdown with nothing in it — a control that looks operable and
    does nothing reads as a broken page, which is exactly how this one read
    when two of its three models carried no variants.
    """
    if not info:
        # Not loaded yet. Saying "no variants" here would be a lie for the
        # first second of every page view, and an alarming one on a page whose
        # whole subject is variants.
        return [], None, True, "Loading the model…"
    variants = info.get("variants") or []
    if not variants:
        return [], None, True, "This model carries no material variants."
    plural = "s" if len(variants) != 1 else ""
    return (
        variants,
        None,
        False,
        f"{len(variants)} variant{plural}: {', '.join(variants)}",
    )


@callback(
    Output("ms-viewer", "variant_name"),
    Input("ms-variant", "value"),
)
def choose_variant(value):
    """Clearing the dropdown must CLEAR the prop, not leave the old value.

    This callback used to `return no_update` when nothing was selected, which
    looked harmless and was not: switching models leaves `ms-variant.value`
    None, so the viewer kept the variant chosen on the *previous* model and
    applied a name the new file does not contain. `"default"` is the GLTF
    default material — the shim drops the attribute entirely for that value,
    which is how model-viewer expresses "no variant".
    """
    return value or "default"
