"""Standalone walk-through for the props no documentation page exercises.

WHY THIS FILE EXISTS
--------------------
The component review for 1.0.0 found that seven ModelViewer props and one Slot
prop appear in no example anywhere on the documentation site — they are
documented and never demonstrated, so nothing would notice if one broke. The
error path had the same shape: the shim listens for ``error`` and writes
``model_state``, but no page offers a free ``src``, so the error payload had
been wired and never observed.

This app covers exactly that gap:

  * ``poster``            — an image stands in until the model is ready
  * ``class_name``        — on ModelViewer AND on a Slot
  * ``min_camera_orbit`` / ``max_camera_orbit``  — dragging is clamped
  * ``min_field_of_view`` / ``max_field_of_view`` — zooming is clamped
  * ``touch_action``      — page scroll vs model gesture (walk it on a PHONE)
  * a deliberately bad ``src`` — so ``model_state``'s error payload is seen

RUNNING IT FROM THE WHEEL
-------------------------
It depends on ``dash`` and ``dash_model_viewer`` and NOTHING else — no
``dash_mantine_components``, no import from this repo's ``lib/``. That is the
point: it must run from a venv that has only the built wheel, which is how it
proves the wheel rather than the checkout.

    python -m build
    python3.12 -m venv /tmp/mv-wheel
    /tmp/mv-wheel/bin/pip install dist/dash_model_viewer-1.0.0-py3-none-any.whl dash
    /tmp/mv-wheel/bin/python examples/manual_walk.py

Then open it in a FOREGROUND tab. A backgrounded tab never loads the model:
``model-viewer`` defaults to ``loading="auto"`` and waits for visibility, which
looks exactly like a broken viewer and is not one.

Assets are public URLs, so there is no ``assets/`` directory to create.
"""
from dash import Dash, Input, Output, html

import dash_model_viewer as dmv

ASTRONAUT = "https://modelviewer.dev/shared-assets/models/Astronaut.glb"
POSTER = "https://modelviewer.dev/assets/poster-astronaut.png"

# A URL that resolves to a 404 rather than a malformed model: the failure under
# test is "the asset is not there", which is the one a user actually hits.
MISSING_MODEL = "https://modelviewer.dev/shared-assets/models/NoSuchModel.glb"

app = Dash(__name__)

# Inline, so `class_name` has something visible to do without an assets/ dir.
app.index_string = """<!DOCTYPE html>
<html>
  <head>
    {%metas%}<title>manual walk — dash-model-viewer</title>{%favicon%}{%css%}
    <style>
      body { font-family: system-ui, sans-serif; margin: 0; padding: 24px;
             max-width: 900px; margin-inline: auto; }
      h2 { margin-top: 32px; }
      pre { background: #f4f4f5; padding: 12px; border-radius: 6px; }
      /* ModelViewer class_name lands HERE — the element is the target. */
      .walk-viewer { border: 3px solid rebeccapurple; border-radius: 12px; }
      /* Slot class_name is added ALONGSIDE the built-in dmv-slot. */
      .walk-hotspot { background: rebeccapurple; color: white; padding: 4px 8px;
                      border-radius: 999px; font-size: 12px; }
    </style>
  </head>
  <body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body>
</html>"""

app.layout = html.Div([
    html.H1("dash-model-viewer — manual walk"),
    html.P("Every prop here is one the documentation site never demonstrates."),

    html.H2("1. poster, class_name, bounds, touch_action"),
    html.P("The purple border is class_name. The poster shows until the model "
           "is ready — reload with a throttled connection to see it longer."),
    dmv.ModelViewer(
        id="walk-viewer",
        src=ASTRONAUT,
        alt="An astronaut model used to walk the undemonstrated props",
        poster=POSTER,
        class_name="walk-viewer",
        camera_controls=True,
        # Clamped deliberately tightly so the limit is obvious in a few seconds
        # of dragging rather than being a subtle edge case.
        min_camera_orbit="-45deg 55deg 1.5m",
        max_camera_orbit="45deg 100deg 4m",
        min_field_of_view="20deg",
        max_field_of_view="40deg",
        # PHONE CHECK: "none" gives every gesture to the model, so the page
        # will NOT scroll while your finger is on the viewer. The default
        # ("pan-y") lets the page scroll vertically through it.
        touch_action="none",
        style={"width": "100%", "height": "420px"},
        children=[
            dmv.Slot(
                id="walk-hotspot",
                slot="hotspot-helmet",
                position="0 1.75 0.15",
                normal="0 1 0",
                class_name="walk-hotspot",
                children="Helmet",
            ),
        ],
    ),
    html.P(id="walk-bounds-readout"),
    html.P(id="walk-hotspot-readout", children="Hotspot clicks: 0"),

    html.H2("2. The error path"),
    html.P("This viewer points at a URL that 404s. The component must report "
           "the failure through model_state and must not crash the page."),
    dmv.ModelViewer(
        id="walk-bad-viewer",
        src=MISSING_MODEL,
        alt="A viewer pointed at a model that does not exist, to show the error state",
        camera_controls=True,
        style={"width": "100%", "height": "260px"},
    ),
    html.Pre(id="walk-error-readout", children="Waiting for the error…"),
])


@app.callback(
    Output("walk-bounds-readout", "children"),
    Input("walk-viewer", "camera"),
)
def show_bounds(camera):
    """Read the camera back so the clamp is legible as numbers, not just feel."""
    if not camera:
        return "Drag and zoom the viewer. Orbit is clamped to ±45deg / 55-100deg / 1.5-4m, field of view to 20-40deg."
    return f"orbit {camera['orbit']}   ·   fov {camera['field_of_view']}"


@app.callback(
    Output("walk-hotspot-readout", "children"),
    Input("walk-hotspot", "n_clicks"),
)
def show_hotspot_clicks(n_clicks):
    return f"Hotspot clicks: {n_clicks or 0}"


@app.callback(
    Output("walk-error-readout", "children"),
    Input("walk-bad-viewer", "model_state"),
)
def show_error(state):
    """The payload nobody has seen. Print it whole rather than summarising it."""
    if not state:
        return "Waiting for the error…"
    if state.get("status") != "error":
        return f"status {state['status']}  ·  progress {state.get('progress')}"
    return (
        f"status   {state['status']}\n"
        f"detail   {state.get('detail') or '(no detail reported)'}\n"
        f"progress {state.get('progress')}"
    )


if __name__ == "__main__":
    app.run(debug=True)
