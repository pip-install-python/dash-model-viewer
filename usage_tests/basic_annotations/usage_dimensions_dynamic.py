# usage_dimensions_dynamic.py
import sys
import os
import dash
from dash import html, dcc, Input, Output, State, clientside_callback, ClientsideFunction

# --- Add project root to sys.path ---
# Calculate the path to the project root directory (adjust '2' if needed)
# This assumes the script is 2 levels down from the project root (root/usage_tests/annotations/script.py)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --- End path modification ---

# Now the import should work
from dash_model_viewer import DashModelViewer

app = dash.Dash(__name__, suppress_callback_exceptions=True, assets_folder="assets")

# Hotspot structure - NO 'children_classname' needed for visibility now
dimension_hotspots_structure = [
    {"slot": "hotspot-dot+X-Y+Z", "normal": "1 0 0", "text": ""}, # Removed children_classname, added text=''
    {"slot": "hotspot-dot+X-Y-Z", "normal": "1 0 0", "text": ""},
    {"slot": "hotspot-dot+X+Y-Z", "normal": "0 1 0", "text": ""},
    {"slot": "hotspot-dot-X+Y-Z", "normal": "0 1 0", "text": ""},
    {"slot": "hotspot-dot-X-Y-Z", "normal": "-1 0 0", "text": ""},
    {"slot": "hotspot-dot-X-Y+Z", "normal": "-1 0 0", "text": ""},
    {"slot": "hotspot-dim+X-Y", "normal": "1 0 0", "text": "", "children_classname": "dim"}, # Keep class for styling
    {"slot": "hotspot-dim+X-Z", "normal": "1 0 0", "text": "", "children_classname": "dim"},
    {"slot": "hotspot-dim+Y-Z", "normal": "0 1 0", "text": "", "children_classname": "dim"},
    {"slot": "hotspot-dim-X-Z", "normal": "-1 0 0", "text": "", "children_classname": "dim"},
    {"slot": "hotspot-dim-X-Y", "normal": "-1 0 0", "text": "", "children_classname": "dim"},
    # Add children_classname="dot" back to dot definitions if needed for CSS styling
    {"slot": "hotspot-dot+X-Y+Z", "normal": "1 0 0", "text": "", "children_classname": "dot"},
    {"slot": "hotspot-dot+X-Y-Z", "normal": "1 0 0", "text": "", "children_classname": "dot"},
    {"slot": "hotspot-dot+X+Y-Z", "normal": "0 1 0", "text": "", "children_classname": "dot"},
    {"slot": "hotspot-dot-X+Y-Z", "normal": "0 1 0", "text": "", "children_classname": "dot"},
    {"slot": "hotspot-dot-X-Y-Z", "normal": "-1 0 0", "text": "", "children_classname": "dot"},
    {"slot": "hotspot-dot-X-Y+Z", "normal": "-1 0 0", "text": "", "children_classname": "dot"},

]

product_options = {
    "Chair": {"src": app.get_asset_url("Froggy_rocking_chair.glb"), "alt": "A 3D model of a rocking chair"},
    "Kara": {"src": app.get_asset_url("kara_-_detroit_become_human.glb"), "alt": "A 3D model of Kara"},
    "Thor": {"src": app.get_asset_url("thor_and_the_midgard_serpent.glb"), "alt": "A 3D model of Thor and Serpent"}
}

# --- MODIFIED: Added ('m', 'm') to the list ---
unit_options = [ {'label': l, 'value': v} for l, v in [('cm','cm'), ('mm','mm'), ('m','m'), ('in','in'), ('ft','ft')] ]
# --- END MODIFICATION ---

app.layout = html.Div([
    html.H1("Dynamic Dimensions Example (Server-Side Visibility Control)"), # Title updated
    html.Div([ # Controls Div
        html.Div([ # Product
            html.Label("Product:", htmlFor="product-select", style={"marginRight": "5px"}),
            dcc.Dropdown( id="product-select", options=[{'label': k, 'value': k} for k in product_options.keys()], value="Chair", clearable=False, style={"width": "150px", "display": "inline-block"} )
        ], style={"display": "inline-block", "marginRight": "20px"}),
        html.Div([ # Checkbox
            html.Label("Show Dimensions:", htmlFor="show-dims-checkbox", style={"marginRight": "5px"}),
            dcc.Checklist( id="show-dims-checkbox", options=[{'label': '', 'value': 'show'}], value=['show'], style={"display": "inline-block"} )
        ], style={"display": "inline-block", "marginRight": "20px"}),
        html.Div([ # Units
             html.Label("Units:", style={"marginRight": "5px"}),
             # RadioItems now uses the updated unit_options list
             dcc.RadioItems( id='unit-select', options=unit_options, value='cm', inline=True, labelStyle={'margin-right': '10px'} )
        ], style={"display": "inline-block"}),
    ], style={"padding": "10px", "border": "1px solid #eee", "marginBottom": "10px"}),

    html.Div( # Container Div
        id="model-container", style={'position': 'relative', 'height': '600px'},
        children=[
            DashModelViewer(
                id="dimension-demo-dynamic",
                src=product_options["Chair"]["src"], alt=product_options["Chair"]["alt"],
                ar=True, arModes="basic_annotations scene-viewer quick-look", arScale="fixed", shadowIntensity=1,
                cameraControls=True, cameraOrbit="-30deg auto auto", maxCameraOrbit="auto 100deg auto", touchAction="pan-y",
                # Initial hotspots are set here, will be overwritten by the new callback
                hotspots=dimension_hotspots_structure,
                style={"height": "100%", "width": "100%", "position": 'absolute', 'top': 0, 'left': 0}
            ),
            # SVG still created by JS
        ]
    ),
    html.P("Dimensions calculated and lines drawn client-side via JavaScript."),
    html.P("Hotspot *presence* controlled server-side by checkbox."), # Updated description
    html.P("CSS for styling '.dot', '.dim', '.dimensionLine' required in assets folder.")
])

# --- Callback to control HOTSPOT LIST based on checkbox ---
@app.callback(
    Output("dimension-demo-dynamic", "hotspots"),
    Input("show-dims-checkbox", "value"),
    # No need to prevent initial call, let it set the initial state
)
def control_hotspot_visibility(checkbox_value):
    if checkbox_value and 'show' in checkbox_value:
        # print("Server Callback: Setting hotspots to structure") # Debug
        return dimension_hotspots_structure # Send the full list
    else:
        # print("Server Callback: Setting hotspots to empty list") # Debug
        return [] # Send an empty list to remove all hotspots

# --- Callback to update model source and alt text ---
@app.callback(
    Output("dimension-demo-dynamic", "src"),
    Output("dimension-demo-dynamic", "alt", allow_duplicate=True),
    Input("product-select", "value"),
    prevent_initial_call=True
)
def update_model_src_dynamic(selected_product):
    if selected_product in product_options:
        return product_options[selected_product]["src"], product_options[selected_product]["alt"]
    return dash.no_update, dash.no_update

# --- Client-side Callback for Calculations, SVG Lines, Units ---
clientside_callback(
    ClientsideFunction(
        namespace='modelViewer',
        function_name='updateDimensions'
    ),
    Output("dimension-demo-dynamic", "alt"), # Dummy output
    Input("dimension-demo-dynamic", "src"),   # Model change
    Input("show-dims-checkbox", "value"),    # Checkbox change (needed for line visibility)
    Input("unit-select", "value"),           # Unit change
    # NEW INPUT: Trigger when the hotspots prop *changes* (server updates it)
    Input("dimension-demo-dynamic", "hotspots"),
    State("dimension-demo-dynamic", "id"),
    State("model-container", "id"),
    prevent_initial_call=False
)

if __name__ == '__main__':
    app.run(debug=True, port=8053)