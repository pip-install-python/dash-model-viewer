# usage_camera_views.py
import sys
import os
import dash
from dash import html, dcc # Import dcc if needed for controls later
import re

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

# --- Define a scaling factor ---
# Should be the same factor used for positions
SCALE_FACTOR = 40

# --- Helper Functions to Scale Target and Orbit Strings ---

def scale_target_string(target_str, factor):
    """Parses 'Xm Ym Zm', scales X, Y, Z, returns 'scaledXm scaledYm scaledZm'."""
    numbers = re.findall(r"[-+]?\d*\.?\d+", target_str) # Find numbers
    if len(numbers) == 3:
        try:
            x = float(numbers[0]) * factor
            y = float(numbers[1]) * factor
            z = float(numbers[2]) * factor
            # Keep sufficient precision and add 'm' suffix back
            return f"{x:.6f}m {y:.6f}m {z:.6f}m"
        except ValueError:
            return target_str # Return original on error
    return target_str # Return original if parsing fails

def scale_orbit_string(orbit_str, radius_factor):
    """Parses 'Thetadeg Phideg Radiusm', scales Radius, returns 'Thetadeg Phideg scaledRadiusm'."""
    parts = orbit_str.split()
    if len(parts) == 3:
        try:
            theta = parts[0] # Keep angle with 'deg'
            phi = parts[1]   # Keep angle with 'deg'
            # Extract number from radius string (e.g., '0.065m')
            radius_num_str = re.findall(r"[-+]?\d*\.?\d+", parts[2])[0]
            scaled_radius = float(radius_num_str) * radius_factor
            # Keep sufficient precision and add 'm' suffix back
            return f"{theta} {phi} {scaled_radius:.8f}m"
        except (ValueError, IndexError):
            return orbit_str # Return original on error
    return orbit_str # Return original if parsing fails


# --- Hotspot Structure for Camera Views ---
# Scaled position, target, and orbit radius values
camera_view_hotspots = [
    {
        "slot": "hotspot-0",
        "position": f"{-0.0569 * SCALE_FACTOR:.4f} {0.0969 * SCALE_FACTOR:.4f} {-0.1398 * SCALE_FACTOR:.4f}",
        "normal": "-0.5829775 0.2863482 -0.7603565",
        # Scale Target and Orbit Radius
        "orbit": scale_orbit_string("-50.94862deg 84.56856deg 0.06545582m", SCALE_FACTOR),
        "target": scale_target_string("-0.04384604m 0.07348397m -0.1213202m", SCALE_FACTOR),
        "text": "The Fighters",
        "children_classname": "view-button"
    },
    {
        "slot": "hotspot-1",
        "position": f"{-0.1997 * SCALE_FACTOR:.4f} {0.11766 * SCALE_FACTOR:.4f} {0.0056 * SCALE_FACTOR:.4f}",
        "normal": "-0.4421014 0.04410423 0.8958802",
        # Scale Target and Orbit Radius
        "orbit": scale_orbit_string("3.711166deg 92.3035deg 0.04335197m", SCALE_FACTOR),
        "target": scale_target_string("-0.1879433m 0.1157161m -0.01563221m", SCALE_FACTOR),
        "text": "Hold Tight!",
        "children_classname": "view-button"
    },
    {
        "slot": "hotspot-2",
        "position": f"{0.0608 * SCALE_FACTOR:.4f} {0.0566 * SCALE_FACTOR:.4f} {0.0605 * SCALE_FACTOR:.4f}",
        "normal": "0.2040984 0.7985359 -0.56629",
        # Scale Target and Orbit Radius
        "orbit": scale_orbit_string("42.72974deg 84.74043deg 0.07104211m", SCALE_FACTOR),
        "target": scale_target_string("0.0757959m 0.04128428m 0.07109568m", SCALE_FACTOR),
        "text": "The Encounter",
        "children_classname": "view-button"
    },
    {
        "slot": "hotspot-3",
        "position": f"{0.1989 * SCALE_FACTOR:.4f} {0.16711 * SCALE_FACTOR:.4f} {-0.0749 * SCALE_FACTOR:.4f}",
        "normal": "0.7045857 0.1997957 -0.6809117",
        # Scale Target and Orbit Radius
        "orbit": scale_orbit_string("-40.11996deg 88.17818deg 0.07090651m", SCALE_FACTOR),
        "target": scale_target_string("0.2011831m 0.1398312m -0.07917573m", SCALE_FACTOR),
        "text": "Catapult",
        "children_classname": "view-button"
    },
    {
        "slot": "hotspot-4",
        "position": f"{0.0677 * SCALE_FACTOR:.4f} {0.18906 * SCALE_FACTOR:.4f} {-0.0158 * SCALE_FACTOR:.4f}",
        "normal": "-0.008245394 0.6207898 0.7839338",
        # Scale Target and Orbit Radius
        "orbit": scale_orbit_string("-118.8446deg 98.83521deg 0.06m", SCALE_FACTOR),
        "target": scale_target_string("0.06528695m 0.1753406m -0.01964653m", SCALE_FACTOR),
        "text": "Thunder and Lightning",
        "children_classname": "view-button"
    },
    {
        "slot": "hotspot-5",
        "position": f"{-0.1418 * SCALE_FACTOR:.4f} {-0.041 * SCALE_FACTOR:.4f} {0.174 * SCALE_FACTOR:.4f}",
        "normal": "-0.4924125 0.4698265 0.7326617",
        # Scale Target and Orbit Radius
        "orbit": scale_orbit_string("-2.305313deg 110.1798deg 0.04504082m", SCALE_FACTOR),
        "target": scale_target_string("-0.1151219m -0.04192762m 0.1523764m", SCALE_FACTOR),
        "text": "Knock Knock",
        "children_classname": "view-button"
    },
    {
        "slot": "hotspot-6",
        "position": f"{0.08414419 * SCALE_FACTOR:.4f} {0.134 * SCALE_FACTOR:.4f} {-0.215 * SCALE_FACTOR:.4f}",
        "normal": "0.03777227 0.06876653 -0.9969176",
        # Scale Target and Orbit Radius
        "orbit": scale_orbit_string("-37.54149deg 82.16209deg 0.0468692m", SCALE_FACTOR),
        "target": scale_target_string("0.08566038m 0.1249514m -0.1939646m", SCALE_FACTOR),
        "text": "Lucky Shot",
        "children_classname": "view-button"
    },
    {
        "slot": "hotspot-7",
        "position": f"{0.14598 * SCALE_FACTOR:.4f} {0.03177 * SCALE_FACTOR:.4f} {-0.05945886 * SCALE_FACTOR:.4f}",
        "normal": "-0.9392524 0.2397608 -0.2456009",
        # Scale Target and Orbit Radius
        "orbit": scale_orbit_string("-142.3926deg 86.45934deg 0.06213665m", SCALE_FACTOR),
        "target": scale_target_string("0.1519967m 0.01904771m -0.05945886m", SCALE_FACTOR),
        "text": "Get Away!",
        "children_classname": "view-button"
    },
    {
        "slot": "hotspot-8",
        "position": f"{0.0094 * SCALE_FACTOR:.4f} {0.0894 * SCALE_FACTOR:.4f} {-0.15103 * SCALE_FACTOR:.4f}",
        "normal": "-0.3878782 0.4957891 -0.7770094",
        # Scale Target and Orbit Radius
        "orbit": scale_orbit_string("-118.6729deg 117.571deg 0.03905975m", SCALE_FACTOR),
        "target": scale_target_string("0.007600758m 0.06771782m -0.1386167m", SCALE_FACTOR),
        "text": "The Jump",
        "children_classname": "view-button"
    },
    {
        "slot": "hotspot-9",
        "position": f"{-0.0658 * SCALE_FACTOR:.4f} {0.1786 * SCALE_FACTOR:.4f} {-0.0183 * SCALE_FACTOR:.4f}",
        "normal": "0.7857152 0.4059967 0.46671",
        # Scale Target and Orbit Radius
        "orbit": scale_orbit_string("53.28236deg 95.91318deg 0.1102844m", SCALE_FACTOR),
        "target": scale_target_string("-0.07579391m 0.1393538m -0.00851791m", SCALE_FACTOR),
        "text": "The Beast",
        "children_classname": "view-button"
    },
    {
        "slot": "hotspot-10",
        "position": f"{0.02610224 * SCALE_FACTOR:.4f} {0.01458751 * SCALE_FACTOR:.4f} {-0.004978945 * SCALE_FACTOR:.4f}",
        "normal": "-0.602551 0.7856147 -0.1405055",
        # Scale Target and Orbit Radius
        "orbit": scale_orbit_string("-78.89725deg 77.17752deg 0.08451112m", SCALE_FACTOR),
        "target": scale_target_string("0.02610223m 0.0145875m -0.004978945m", SCALE_FACTOR),
        "text": "Treasure",
        "children_classname": "view-button"
    },
    {
        "slot": "hotspot-11",
        "position": f"{-0.1053838 * SCALE_FACTOR:.4f} {0.01610652 * SCALE_FACTOR:.4f} {0.1076345 * SCALE_FACTOR:.4f}",
        "normal": "-0.624763 0.5176854 0.5845283",
        # Scale Target and Orbit Radius
        "orbit": scale_orbit_string("10.89188deg 119.9775deg 0.03543022m", SCALE_FACTOR),
        "target": scale_target_string("-0.1053838m 0.01610652m 0.1076345m", SCALE_FACTOR),
        "text": "Desperation",
        "children_classname": "view-button"
    },
]

# Initial Camera View might also need scaling? Let's scale the radius for consistency
# Original Orbit: "-8.142746deg 68.967deg 0.6179899m"
# Original Target: "-0.003m 0.0722m 0.0391m"
initial_orbit = scale_orbit_string("-8.142746deg 68.967deg 0.6179899m", SCALE_FACTOR)
initial_target = scale_target_string("-0.003m 0.0722m 0.0391m", SCALE_FACTOR)


app.layout = html.Div([
    html.H1("Camera Views via Hotspot Clicks"),
    DashModelViewer(
        id="hotspot-camera-view-demo",
        # --- Model ---
        src=app.get_asset_url("thor_and_the_midgard_serpent.glb"),
        alt="Thor and the Midgard Serpent",
        poster=app.get_asset_url("ThorAndTheMidgardSerpent.webp"),
        # --- Controls & Interaction ---
        cameraControls=True,
        touchAction="none",
        # Use scaled initial view
        cameraOrbit=initial_orbit,
        cameraTarget=initial_target,
        fieldOfView="45deg",
        minFieldOfView="25deg",
        maxFieldOfView="45deg",
        interpolationDecay=200,
        # Min orbit radius uses percentage, likely okay without scaling
        minCameraOrbit="auto auto 5%",
        # --- AR & Rendering ---
        ar=True,
        toneMapping="aces",
        shadowIntensity=1,
        # --- Hotspots ---
        hotspots=camera_view_hotspots, # Pass the fully scaled list
        # --- Style ---
        style={'width': '800px', 'height': '600px', 'margin': 'auto'}
    ),
    html.P("Click the buttons (hotspots) to change the camera view."),
    html.P("Styling for '.view-button' defined in assets/camera_views_styles.css."),
    html.P("Interaction logic (reading data-orbit/data-target and updating camera) is handled within the React component.")
])

if __name__ == '__main__':
    app.run(debug=True, port=8034)