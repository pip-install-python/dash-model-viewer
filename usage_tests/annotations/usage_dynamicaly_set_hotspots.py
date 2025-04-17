# usage_dynamicaly_set_hotspots.py
# (Keep the sys.path modification and imports)
import sys
import os
import dash
from dash import html, dcc, Input, Output, State, clientside_callback, ClientsideFunction, no_update
import time
import json # To handle data from JS

# --- Add project root to sys.path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --- End path modification ---

from dash_model_viewer import DashModelViewer # Now the import should work

# Make sure assets folder is correctly identified relative to this script's location
# If assets is in project_root, this should work if script is run from root
app = dash.Dash(__name__, suppress_callback_exceptions=True, assets_folder="assets")

print(f"Dash Assets Folder Path: {app.config.assets_folder}")

# Initial model
INITIAL_MODEL_SRC = "https://modelviewer.dev/shared-assets/models/Astronaut.glb"
INITIAL_MODEL_ALT = "A 3D model of an astronaut"

app.layout = html.Div([
    html.H1("Dynamically Adding Hotspots"),

    # -- Stores --
    dcc.Store(id='hotspot-store', data=[]),
    dcc.Store(id='mode-store', data='viewing'),
    dcc.Store(id='new-hotspot-data-store', data=None),

    # -- Controls --
    html.Div([
        # This button toggles between "Set Hotspot" and "Place Hotspot" modes
        html.Button("Set Hotspot", id="set-place-hotspot-button", n_clicks=0),
        # This button cancels the adding mode
        html.Button("Cancel", id="cancel-hotspot-button", n_clicks=0, style={'display': 'none', 'marginLeft': '10px'}),
        dcc.Input(
            id="hotspot-label-input",
            type="text",
            placeholder="Enter hotspot label...",
            # Add initial value to prevent uncontrolled warning
            value="",
            style={'display': 'none', 'marginLeft': '10px'} # Initially hidden
        ),
    ], style={'marginBottom': '10px'}),

    # -- Model Viewer Container --
    html.Div(
        id="viewer-container",
        style={'position': 'relative', 'height': '600px', 'width': '800px', 'border': '1px solid lightgrey', 'margin': 'auto'},
        children=[
            DashModelViewer(
                id="dynamic-hotspot-viewer",
                src=INITIAL_MODEL_SRC,
                alt=INITIAL_MODEL_ALT,
                cameraControls=True,
                ar=True,
                style={"height": "100%", "width": "100%", "position": 'absolute', 'top': 0, 'left': 0},
                hotspots=[] # Start with empty list, updated by callback
            ),
            # Visual reticle - centered overlay, shown only in 'adding' mode
            html.Div(id="reticle", className="reticle", style={'display': 'none'})
        ]
    ),

    html.P("Click 'Set Hotspot', type a label, position the reticle, then click 'Place Hotspot'."),
    html.P("Requires 'model_viewer_clientside.js' and CSS for '.reticle' / '.hotspot-dynamic' in assets folder.")
])

# --- Callbacks ---

# Callback 1: Enter Add Mode when "Set Hotspot" is clicked
@app.callback(
    Output('mode-store', 'data', allow_duplicate=True),
    Output('hotspot-label-input', 'style', allow_duplicate=True),
    Output('set-place-hotspot-button', 'children', allow_duplicate=True),
    Output('cancel-hotspot-button', 'style'), # Show Cancel button
    Output('reticle', 'style', allow_duplicate=True), # Show reticle
    Input('set-place-hotspot-button', 'n_clicks'),
    State('mode-store', 'data'),
    prevent_initial_call=True
)
def enter_add_mode(n_clicks_set, current_mode):
    # This callback ONLY enters add mode. Placement is handled by the clientside callback
    # triggered by this same button when its text is "Place Hotspot".
    # The cancel button handles exiting add mode.
    if current_mode == 'viewing':
        print("Entering add mode")
        # Enter adding mode
        return 'adding', {'display': 'inline-block', 'marginLeft': '10px'}, "Place Hotspot", {'display': 'inline-block', 'marginLeft': '10px'}, {'display': 'block'}
    else:
        # If already in 'adding' mode, clicking "Place Hotspot" triggers the
        # clientside callback, which then triggers Callback 2. Don't change state here.
        print("Place Hotspot button clicked (handled by clientside)")
        return no_update, no_update, no_update, no_update, no_update

# Callback 1.5: Exit Add Mode when "Cancel" is clicked
@app.callback(
    Output('mode-store', 'data', allow_duplicate=True),
    Output('hotspot-label-input', 'style', allow_duplicate=True),
    Output('hotspot-label-input', 'value', allow_duplicate=True), # Clear input on cancel
    Output('set-place-hotspot-button', 'children', allow_duplicate=True),
    Output('cancel-hotspot-button', 'style', allow_duplicate=True), # Hide Cancel
    Output('reticle', 'style', allow_duplicate=True), # Hide reticle
    Input('cancel-hotspot-button', 'n_clicks'),
    prevent_initial_call=True
)
def cancel_add_mode(n_clicks_cancel):
    print("Cancelling add mode")
    # Exit adding mode
    return 'viewing', {'display': 'none', 'marginLeft': '10px'}, "", "Set Hotspot", {'display': 'none', 'marginLeft': '10px'}, {'display': 'none'}


# Callback 2: Process New Hotspot Data received from Client-Side
@app.callback(
    Output('hotspot-store', 'data', allow_duplicate=True), # Update the main store
    Output('mode-store', 'data', allow_duplicate=True),    # Reset mode
    Output('hotspot-label-input', 'value', allow_duplicate=True), # Clear input
    Output('hotspot-label-input', 'style', allow_duplicate=True), # Hide input
    Output('set-place-hotspot-button', 'children', allow_duplicate=True), # Reset button
    Output('cancel-hotspot-button', 'style', allow_duplicate=True),    # Hide Cancel button
    Output('reticle', 'style', allow_duplicate=True),            # Hide reticle
    Input('new-hotspot-data-store', 'data'),             # Triggered by JS
    State('hotspot-store', 'data'),                      # Get current list
    prevent_initial_call=True
)
def add_new_hotspot(new_hotspot_data, current_hotspots):
    # This is triggered *after* the clientside callback returns data
    if new_hotspot_data is None or not isinstance(new_hotspot_data, dict):
        print("Invalid or no new hotspot data received.")
        return no_update, no_update, no_update, no_update, no_update, no_update, no_update

    print(f"Received new hotspot data: {new_hotspot_data}") # Debug

    # Add the new hotspot to the list
    if isinstance(current_hotspots, list):
         current_hotspots.append(new_hotspot_data)
         new_list = current_hotspots
    else:
         print("Initializing hotspot list.")
         new_list = [new_hotspot_data] # Initialize list if empty/invalid

    # Reset UI elements back to viewing state
    return new_list, 'viewing', "", {'display': 'none', 'marginLeft': '10px'}, "Set Hotspot", {'display': 'none', 'marginLeft': '10px'}, {'display': 'none'}


# Callback 3: Update ModelViewer hotspots prop when store changes
@app.callback(
    Output('dynamic-hotspot-viewer', 'hotspots'),
    Input('hotspot-store', 'data')
)
def update_viewer_hotspots(hotspot_list):
    print(f"Updating viewer hotspots: {hotspot_list}") # Debug
    return hotspot_list or []


# --- Client-Side Callback ---
# Handles click on the "Place Hotspot" button to get position/normal and send data back
clientside_callback(
    ClientsideFunction(namespace='modelViewer', function_name='handleAddHotspotClick'),
    Output('new-hotspot-data-store', 'data'),       # Output to trigger server callback 2
    # Trigger ONLY when the main button is clicked
    Input('set-place-hotspot-button', 'n_clicks'),
    State('dynamic-hotspot-viewer', 'id'), # Pass the viewer ID to JS
    State('mode-store', 'data'),           # Check if in 'adding' mode
    State('hotspot-label-input', 'value'), # Get the label text
    prevent_initial_call=True
)


if __name__ == '__main__':
    # Assumes assets folder is in the project root relative to where python is run
    app.run(debug=True, port=8055) # Changed port just in case