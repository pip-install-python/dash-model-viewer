# usage_webxr.py
import dash
from dash import html, Input, Output, State, callback, clientside_callback
from dash_model_viewer import DashModelViewer  # Import your Dash component

# --- Model Data ---
# Using absolute URLs from the example
# If using local files, place them in assets and use app.get_asset_url()
MODEL_DATA = {
    "Chair": {
        "src": "assets/Froggy_rocking_chair.glb",
        "poster": "assets/frog_rocking_chair.png",
        "alt": "A 3D model of a chair"
    },
    "Mixer": {
        "src": "assets/kara_-_detroit_become_human.glb",
        "poster": "assets/kara.png",
        "alt": "A 3D model of a mixer"
    },
    "GeoPlanter": {
        "src": "assets/thor_and_the_midgard_serpent.glb",
        "poster": "assets/thor.png",
        "alt": "A 3D model of a geometric planter"
    },
    "Shoe": {
        "src": "assets/MaterialsVariantsShoe.glb",
        "poster": "assets/shoe.png",
        "alt": "A 3D model of a sofa"
    },

}
INITIAL_MODEL = "Chair"

app = dash.Dash(__name__, suppress_callback_exceptions=True)

# Prepare slider buttons
slider_buttons = []
for i, name in enumerate(MODEL_DATA.keys()):
    button = html.Button(
        id={"type": "model-select-button", "index": i},
        className=f"slide {'selected' if name == INITIAL_MODEL else ''}",
        style={"backgroundImage": f"url('{MODEL_DATA[name]['poster']}')"},
        **{"data-model-name": name} # Use data-* attribute to store model name
    )
    slider_buttons.append(button)

app.layout = html.Div([
    html.H1("WebXR Demo with Model Viewer and Dash"),

    DashModelViewer(
        id="model-viewer-xr",
        # --- Core Attributes ---
        src=MODEL_DATA[INITIAL_MODEL]["src"],
        poster=MODEL_DATA[INITIAL_MODEL]["poster"],
        alt=MODEL_DATA[INITIAL_MODEL]["alt"],
        # --- AR Attributes ---
        ar=True,
        arModes="basic_annotations scene-viewer quick-look", # Default behavior
        arScale="auto",
        # --- Interaction Attributes ---
        cameraControls=True,
        touchAction="pan-y", # Default
        shadowIntensity=1.0, # Assuming your component supports this mapping
        # --- Custom Slot Content via Props ---
        # For ar-button, the React component uses a prop, not a direct slot child
        arButtonText="View in your space",
        # Pass Dash components for custom AR prompts/failures
        customArPrompt=html.Img(src=app.get_asset_url("hand.png"), id="ar-prompt-img"),
        customArFailure=html.Div("AR is not tracking!", id="ar-failure-msg"),
        # --- Style ---
        style={"height": "600px", "width": "100%"} # Style directly or via CSS
    ),

    # --- Slider outside ModelViewer ---
    html.Div(
        id="slider-container",
        className="slider-container", # Class for CSS
        children=[
            html.Div(className="slides", children=slider_buttons)
        ]
    ),

    # Store the currently selected model name
    dash.dcc.Store(id='current-model-name', data=INITIAL_MODEL)
])

@callback(
    Output('model-viewer-xr', 'src'),
    Output('model-viewer-xr', 'poster'),
    Output('model-viewer-xr', 'alt'),
    Output('current-model-name', 'data'),
    Input({"type": "model-select-button", "index": dash.ALL}, 'n_clicks'),
    State({"type": "model-select-button", "index": dash.ALL}, 'data-model-name'),
    prevent_initial_call=True
)
def switch_model(n_clicks, model_names):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    # Get the index of the button that was clicked
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    # The button_id is a JSON string like '{"index":2,"type":"model-select-button"}'
    import json
    try:
        index_clicked = json.loads(button_id)['index']
        selected_model_name = model_names[index_clicked]

        if selected_model_name in MODEL_DATA:
            new_src = MODEL_DATA[selected_model_name]["src"]
            new_poster = MODEL_DATA[selected_model_name]["poster"]
            new_alt = MODEL_DATA[selected_model_name]["alt"]
            return new_src, new_poster, new_alt, selected_model_name
        else:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    except (json.JSONDecodeError, IndexError, KeyError):
         return dash.no_update, dash.no_update, dash.no_update, dash.no_update


# Clientside callback to update the 'selected' class on slider buttons
clientside_callback(
    """
    function(currentModelName, buttonDataModelNames) {
        const buttons = document.querySelectorAll('.slide');
        buttons.forEach((button, index) => {
            // Assuming buttonDataModelNames corresponds correctly to buttons by index
            if (buttonDataModelNames && buttonDataModelNames[index] === currentModelName) {
                button.classList.add('selected');
            } else {
                button.classList.remove('selected');
            }
        });
        return window.dash_clientside.no_update; // No output needed
    }
    """,
    Output({"type": "model-select-button", "index": dash.ALL}, 'className'), # Dummy output
    Input('current-model-name', 'data'),
    State({"type": "model-select-button", "index": dash.ALL}, 'data-model-name'),
)

# Note: The original example had JS to prevent slider interaction during AR:
# document.querySelector(".slider").addEventListener('beforexrselect', (ev) => {
#   ev.preventDefault();
# });
# Replicating this exact behavior might require a more complex clientside callback
# listening to model-viewer's AR events or potentially modifying the React component.

if __name__ == '__main__':
    app.run(debug=True, port=5232)