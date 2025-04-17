# usage_basic_annotations.py
import sys
import os
import dash
from dash import html, dcc # Import dcc if needed for controls later

# --- Add project root to sys.path ---
# Calculate the path to the project root directory (adjust '2' if needed)
# This assumes the script is 2 levels down from the project root (root/usage_tests/annotations/script.py)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --- End path modification ---

# Now the import should work
from dash_model_viewer import DashModelViewer

app = dash.Dash(__name__, suppress_callback_exceptions=True)

# Data for the Astronaut hotspots
astronaut_hotspots = [
    {
        "slot": "hotspot-visor",
        "position": "0 1.75 0.35",
        "normal": "0 0 1",
        "text": "Visor" # Use text for the content inside the hotspot div
    },
    {
        "slot": "hotspot-hand",
        "position": "-0.54 0.93 0.1",
        "normal": "-0.73 0.05 0.69",
        # Use text. Complex children cannot be passed this way.
        # The text will appear *inside* the hotspot element itself.
        # Styling the annotation box separately requires CSS targeting
        # the slot or more advanced techniques.
        "text": "Hand"
    },
    {
        "slot": "hotspot-foot",
        "position": "0.16 0.1 0.17",
        "normal": "-0.07 0.97 0.23",
        "text": "Foot" # Use text here as well
    },
]

app.layout = html.Div([
    html.H1("Basic Hotspots and Annotations"),
    DashModelViewer(
        id="astronaut-demo",
        # --- Core Attributes ---
        src="https://modelviewer.dev/shared-assets/models/Astronaut.glb",
        alt="A 3D model of an astronaut",
        poster="https://modelviewer.dev/assets/poster-astronaut.webp",
        # --- Staging & AR ---
        ar=True,
        arModes="basic_annotations scene-viewer quick-look", # Correct prop name: arModes
        toneMapping="aces", # Correct prop name: toneMapping
        shadowIntensity=1, # Correct prop name: shadowIntensity
        # --- Camera & Interaction ---
        cameraControls=True,
        touchAction="pan-y",
        # --- Hotspots ---
        # Pass the list of dictionaries with simple text.
        hotspots=astronaut_hotspots,
        # --- Style ---
        style={"height": "600px", "width": "100%", "border": "1px solid #ccc"}
    ),
    html.P("Annotations text appears inside the hotspot elements. Styling is controlled by CSS."),
    html.P("Refer to assets/model-viewer-styles.css for specific styles like `.hotspot`, `.annotation` (if used via CSS pseudo-elements), and slot-specific rules like `.hotspot[slot='hotspot-hand']`."),
    html.P(html.Strong("Note:"))
])

# Ensure CSS in assets/model-viewer-styles.css targets slots correctly:
# .hotspot[slot="hotspot-hand"] { background-color: red; --min-hotspot-opacity: 0; }
# You might add ::after pseudo-element to .hotspot[slot="hotspot-hand"] to display the annotation text visually separated.

if __name__ == '__main__':
    app.run(debug=True, port=8051)