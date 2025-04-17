# dash-model-viewer

[![PyPI version](https://badge.fury.io/py/dash-model-viewer.svg)](https://badge.fury.io/py/dash-model-viewer) <!-- Add link when published -->
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**Embed interactive 3D models directly into your Dash applications with Augmented Reality (AR) support.**

![Dash Model Viewer Demo](assets/Dash-model-viewer.gif)

`dash-model-viewer` is a Dash component library that wraps Google's `<model-viewer>` web component, allowing you to easily display and interact with 3D models (.glb, .gltf) within your Python Dash dashboards. 

**Key Features:**

*   **Simple 3D Model Display:** Easily load and display 3D models from URLs.
*   **Interactive Controls:** Built-in camera controls (orbit, pan, zoom) and customizable interaction options.
*   **Augmented Reality (AR):** View models in your physical space on supported devices using WebXR.
*   **Annotations & Hotspots:** Define interactive points on your model to display information or trigger actions.
*   **Dynamic Updates:** Change model source, camera views, hotspots, and other properties dynamically using Dash callbacks.
*   **Customization:** Control appearance, lighting, AR behavior, and more through component properties.
*   **Client-Side Interaction:** Extend functionality with custom JavaScript for complex interactions like dynamic dimensions or interactive hotspot placement.

---
## Interactive Documentation
https://pip-install-python.com/pip/dash_model_viewer

---
## Table of Contents

*   [Installation](#installation)
*   [Quick Start](#quick-start)
*   [Usage Examples](#usage-examples)
    *   [Basic Annotations](#basic-annotations)
    *   [Camera Views via Hotspots](#camera-views-via-hotspots)
    *   [Dynamic Model Switching](#dynamic-model-switching)
    *   [AR Customization (WebXR)](#ar-customization-webxr)
    *   [Advanced: Dynamic Dimensions](#advanced-dynamic-dimensions)
    *   [Advanced: Interactive Hotspot Placement](#advanced-interactive-hotspot-placement)
*   [Component Properties (API Reference)](#component-properties-api-reference)
*   [Client-Side Scripting](#client-side-scripting)
*   [Styling](#styling)
*   [Contributing](#contributing)
*   [License](#license)
*   [Acknowledgements](#acknowledgements)

---

## Installation

1.  **Install Dash:** If you haven't already, install Dash and its core dependencies:
    ```bash
    pip install dash dash-bootstrap-components
    ```

2.  **Install dash-model-viewer:**
    ```bash
    pip install dash-model-viewer
    ```
    *(Replace with the correct package name once published on PyPI)*

---

## Quick Start

Here's a minimal example to get you started:

```python
# app.py
import dash
from dash import html
from dash_model_viewer import DashModelViewer

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("My First 3D Model in Dash"),
    DashModelViewer(
        id="my-viewer",
        src="https://modelviewer.dev/shared-assets/models/Astronaut.glb", # URL to your .glb or .gltf file
        alt="A 3D model of an astronaut",
        cameraControls=True,  # Enable mouse/touch controls
        ar=True,              # Enable the AR button
        style={"width": "80%", "height": "600px", "margin": "auto"}
    )
])

if __name__ == '__main__':
    app.run_server(debug=True)
```

This will display the Astronaut model with camera controls and an AR button (if viewed on a supported device).

---

## Usage Examples

### Basic Annotations

Use the `hotspots` property to add annotations. The `text` field will be displayed inside the hotspot `div`. Styling requires CSS (see [Styling](#styling)).

```python
# usage_basic_annotations.py (simplified)
import dash
from dash import html
from dash_model_viewer import DashModelViewer

app = dash.Dash(__name__, assets_folder="assets") # Ensure 'assets' folder exists

astronaut_hotspots = [
    {
        "slot": "hotspot-visor",      # Unique identifier for the slot
        "position": "0 1.75 0.35",    # World-space coordinates (X Y Z)
        "normal": "0 0 1",            # Surface normal vector (optional, affects orientation)
        "text": "Visor"               # Text content for the annotation
    },
    {
        "slot": "hotspot-hand",
        "position": "-0.54 0.93 0.1",
        "normal": "-0.73 0.05 0.69",
        "text": "Left Hand"
    },
]

app.layout = html.Div([
    html.H1("Model with Annotations"),
    DashModelViewer(
        id="astronaut-annotated",
        src="https://modelviewer.dev/shared-assets/models/Astronaut.glb",
        alt="Astronaut with annotations",
        cameraControls=True,
        ar=True,
        hotspots=astronaut_hotspots, # Pass the list of hotspots
        style={"height": "600px", "width": "100%"}
    ),
    html.P("Requires CSS in assets/your_styles.css to style .hotspot elements.")
])

if __name__ == '__main__':
    app.run_server(debug=True, port=8051)
```

*(See `usage_basic_annotations.py` for the full example and required CSS)*

### Camera Views via Hotspots

You can use hotspots to trigger camera view changes. Define `orbit` and `target` data attributes within the `hotspots` prop. The component's internal JavaScript handles the click event to update the camera.

```python
# usage_camera_views.py (simplified)
# ... (imports and app setup) ...

# Note: Values might need scaling depending on your model
SCALE_FACTOR = 1 # Adjust if needed based on your model scale

camera_view_hotspots = [
    {
        "slot": "hotspot-view-1",
        "position": f"{-0.05 * SCALE_FACTOR} {0.1 * SCALE_FACTOR} {-0.14 * SCALE_FACTOR}",
        "normal": "-0.58 0.28 -0.76",
        # These data-* attributes are used by the component's internal JS
        "orbit": f"-50deg 84deg {0.06 * SCALE_FACTOR}m", # Theta Phi Radius
        "target": f"{-0.04 * SCALE_FACTOR}m {0.07 * SCALE_FACTOR}m {-0.12 * SCALE_FACTOR}m", # X Y Z
        "text": "View 1",
        "children_classname": "view-button" # Optional class for styling
    },
    # ... more camera view hotspots ...
]

app.layout = html.Div([
    html.H1("Click Hotspots to Change View"),
    DashModelViewer(
        id="hotspot-camera-demo",
        src=app.get_asset_url("your_model.glb"), # Example local model
        alt="Model with camera views",
        cameraControls=True,
        # Define initial view if desired
        # cameraOrbit="..."
        # cameraTarget="..."
        interpolationDecay=200, # Smoother transition
        hotspots=camera_view_hotspots,
        style={'width': '800px', 'height': '600px', 'margin': 'auto'}
    ),
    html.P("Click the buttons (hotspots) to change the camera.")
])

# ... (run server) ...
```

*(See `usage_camera_views.py` for the full example, including scaling helpers and required CSS)*

### Dynamic Model Switching

Update the `src` property via a Dash callback to load different models.

```python
# usage.py (simplified)
import dash
from dash import html, Input, Output, callback
from dash_model_viewer import DashModelViewer

app = dash.Dash(__name__)

MODELS = {
    "Astronaut": "https://modelviewer.dev/shared-assets/models/Astronaut.glb",
    "Helmet": "https://modelviewer.dev/shared-assets/models/DamagedHelmet.glb"
}

app.layout = html.Div([
    html.H1("Switch Models Dynamically"),
    DashModelViewer(
        id="dynamic-model-viewer",
        src=MODELS["Astronaut"], # Initial model
        alt="A 3D model",
        cameraControls=True,
        ar=True,
        style={"height": "600px", "width": "100%"},
    ),
    html.Button('Load Astronaut', id='btn-astronaut', n_clicks=0),
    html.Button('Load Helmet', id='btn-helmet', n_clicks=0),
])

@callback(
    Output('dynamic-model-viewer', 'src'),
    Input('btn-astronaut', 'n_clicks'),
    Input('btn-helmet', 'n_clicks')
)
def update_model(astro_clicks, helmet_clicks):
    triggered_id = dash.callback_context.triggered_id
    if triggered_id == 'btn-helmet':
        return MODELS["Helmet"]
    else: # Default or astronaut button
        return MODELS["Astronaut"]

if __name__ == '__main__':
    app.run_server(debug=True, port=5431)
```

*(See `usage.py` for the full example)*

### AR Customization (WebXR)

Customize the AR experience using properties like `arButtonText`, `customArPrompt`, and `customArFailure`. You can pass simple text or other Dash components into the prompt/failure slots.

```python
# usage_webxr.py (simplified)
import dash
from dash import html, dcc, Input, Output, callback, State, clientside_callback
from dash_model_viewer import DashModelViewer

app = dash.Dash(__name__, assets_folder="assets") # Ensure 'assets' folder exists

INITIAL_MODEL_SRC = app.get_asset_url("Froggy_rocking_chair.glb") # Example local
INITIAL_MODEL_POSTER = app.get_asset_url("frog_rocking_chair.png")

app.layout = html.Div([
    html.H1("Custom AR Experience"),
    DashModelViewer(
        id="model-viewer-xr",
        src=INITIAL_MODEL_SRC,
        poster=INITIAL_MODEL_POSTER,
        alt="A 3D model",
        ar=True,
        arModes="webxr scene-viewer quick-look",
        cameraControls=True,
        shadowIntensity=1.0,
        # Customizations
        arButtonText="Place in Your Room",
        customArPrompt=html.Div([ # Example using Dash components
            html.Img(src=app.get_asset_url("custom_hand_icon.png"), style={'height': '40px'}),
            html.P("Move your phone to scan the floor...")
        ]),
        customArFailure=html.Div("AR failed to start. Ensure your browser supports WebXR.", style={'color': 'red'}),
        style={"height": "600px", "width": "100%"}
    ),
    # ... (Add controls like sliders if needed, see full example)
])

# ... (Callbacks for model switching if using controls) ...

if __name__ == '__main__':
    app.run_server(debug=True, port=5232)
```

*(See `usage_webxr.py` for the full example with a model switching slider and required CSS/JS)*

### Advanced: Dynamic Dimensions

This example demonstrates controlling hotspot *visibility* from the server and using **client-side JavaScript** in your `assets` folder to calculate model dimensions and draw SVG lines between hotspots.

**Requires:**
1.  Python code (`usage_dimensions_dynamic.py`) to manage hotspot visibility via callbacks.
2.  JavaScript file (e.g., `assets/model_viewer_clientside.js`) with functions like `updateDimensions`.
3.  CSS file (e.g., `assets/dimensions_styles.css`) to style hotspots (`.dot`, `.dim`) and SVG lines (`.dimensionLine`).

```python
# usage_dimensions_dynamic.py (Conceptual Snippet)
# ... imports ...
app = dash.Dash(__name__, assets_folder="assets")

# Define base hotspot structure (positions will be set by JS)
dimension_hotspots_structure = [
    {"slot": "hotspot-dot+X-Y+Z", "normal": "1 0 0", "text": "", "children_classname": "dot"},
    # ... other dots ...
    {"slot": "hotspot-dim+X-Y", "normal": "1 0 0", "text": "", "children_classname": "dim"},
    # ... other dimension display hotspots ...
]

app.layout = html.Div([
    # ... Controls (Dropdown, Checkbox for Show/Hide, Units Radio) ...
    html.Div(id="model-container", style={'position': 'relative', 'height': '600px'}, children=[
        DashModelViewer(
            id="dimension-demo-dynamic",
            # ... src, alt, cameraControls etc. ...
            hotspots=[], # Start empty, controlled by callback
            style={"height": "100%", "width": "100%"}
        ),
        # SVG overlay is usually added/manipulated by the client-side JS
    ]),
])

# Python Callback: Controls which hotspots are sent to the component
@app.callback(
    Output("dimension-demo-dynamic", "hotspots"),
    Input("show-dims-checkbox", "value")
)
def control_hotspot_visibility(show_dims):
    if show_dims and 'show' in show_dims:
        return dimension_hotspots_structure # Send full list to JS
    else:
        return [] # Send empty list to hide

# Client-side Callback: Triggers JS function to calculate/draw
clientside_callback(
    ClientsideFunction(namespace='modelViewer', function_name='updateDimensions'),
    Output("dimension-demo-dynamic", "alt"), # Dummy output
    Input("dimension-demo-dynamic", "src"),
    Input("show-dims-checkbox", "value"),
    Input("unit-select", "value"),
    Input("dimension-demo-dynamic", "hotspots"), # Trigger when list changes
    State("dimension-demo-dynamic", "id"),
    State("model-container", "id"),
)

# ... (Callback to update model src) ...
# ... (run server) ...
```

*(See `usage_dimensions_dynamic.py` and corresponding JS/CSS in your project for the full implementation details. The JS needs to use `<model-viewer>`'s API like `getBoundingBoxCenter()`, `getDimensions()`, and potentially `positionAndNormalFromPoint()` to place hotspots and draw lines.)*

### Advanced: Interactive Hotspot Placement

This example uses a combination of Dash callbacks, dcc.Store, and **client-side JavaScript** to allow users to place new hotspots onto the model interactively.

**Requires:**
1.  Python code (`usage_dynamicaly_set_hotspots.py`) with multiple callbacks and stores to manage state ('viewing' vs 'adding').
2.  JavaScript file (e.g., `assets/model_viewer_clientside.js`) with a function like `handleAddHotspotClick`.
3.  CSS file (e.g., `assets/dynamic_hotspots.css`) for the reticle and newly added hotspots.

```python
# usage_dynamicaly_set_hotspots.py (Conceptual Snippet)
# ... imports ...
app = dash.Dash(__name__, assets_folder="assets")

app.layout = html.Div([
    # ... Stores (hotspot-store, mode-store, new-hotspot-data-store) ...
    # ... Controls (Set/Place Button, Cancel Button, Label Input) ...
    html.Div(id="viewer-container", children=[
        DashModelViewer(
            id="dynamic-hotspot-viewer",
            # ... src, alt, cameraControls ...
            hotspots=[], # Initial empty list
        ),
        html.Div(id="reticle", className="reticle", style={'display': 'none'}) # Visual guide
    ]),
])

# --- Callbacks ---
# 1. Python: Enter Add Mode (show input/reticle, change button text)
# 2. Python: Cancel Add Mode
# 3. Client-side: Handle "Place Hotspot" click
#    - Uses model-viewer API (`positionAndNormalFromPoint`) to get coords/normal.
#    - Gets label from input.
#    - Sends data back to Dash via `new-hotspot-data-store`.
# 4. Python: Process New Hotspot Data (add to `hotspot-store`, reset UI)
# 5. Python: Update ModelViewer `hotspots` prop when `hotspot-store` changes

# Client-side Callback Setup
clientside_callback(
    ClientsideFunction(namespace='modelViewer', function_name='handleAddHotspotClick'),
    Output('new-hotspot-data-store', 'data'),
    Input('set-place-hotspot-button', 'n_clicks'),
    State('dynamic-hotspot-viewer', 'id'),
    State('mode-store', 'data'),
    State('hotspot-label-input', 'value'),
    prevent_initial_call=True
)

# ... (Implement Python callbacks 1, 2, 4, 5) ...
# ... (run server) ...
```

*(See `usage_dynamicaly_set_hotspots.py` and corresponding JS/CSS for the full implementation. The JS function needs to interact with the `<model-viewer>` element to get placement data when the user clicks.)*

---

## Component Properties (API Reference)

| Property           | Type                                | Default                                    | Description                                                                                                |
| :----------------- | :---------------------------------- | :----------------------------------------- | :--------------------------------------------------------------------------------------------------------- |
| **`id`**           | `string`                            | **Required**                               | Unique identifier for the component.                                                                       |
| **`src`**          | `string`                            | **Required**                               | URL to the 3D model file (.glb, .gltf).                                                                    |
| **`alt`**          | `string`                            | **Required**                               | Alternative text description for accessibility.                                                            |
| `style`            | `object`                            | `{}`                                       | Standard CSS styles for the outer container.                                                               |
| `cameraControls`   | `bool`                              | `True`                                     | Enable user interaction to control the camera (orbit, zoom, pan).                                          |
| `touchAction`      | `'pan-y'`, `'pan-x'`, `'none'`      | `'pan-y'`                                  | How touch gestures interact with the model (vertical pan, horizontal pan, or none).                          |
| `cameraOrbit`      | `string`                            | `undefined`                                | Sets the initial camera position (`"theta phi radius"`, e.g., `"0deg 75deg 1.5m"`).                           |
| `cameraTarget`     | `string`                            | `undefined`                                | Sets the point the camera looks at (`"X Y Z"`, e.g., `"0m 1m 0m"`).                                        |
| `fieldOfView`      | `string`                            | `'auto'`                                   | Camera's vertical field of view (e.g., `'45deg'`).                                                         |
| `minFieldOfView`   | `string`                            | `'25deg'`                                  | Minimum vertical field of view allowed.                                                                    |
| `maxFieldOfView`   | `string`                            | `'auto'`                                   | Maximum vertical field of view allowed.                                                                    |
| `interpolationDecay`| `number` or `string`                | `50`                                       | Controls the speed of camera transitions (higher is faster).                                               |
| `minCameraOrbit`   | `string`                            | `'auto auto auto'`                         | Sets minimum bounds for camera orbit (`"theta phi radius"`, use 'auto' for no limit).                        |
| `maxCameraOrbit`   | `string`                            | `'auto auto auto'`                         | Sets maximum bounds for camera orbit.                                                                      |
| `poster`           | `string`                            | `undefined`                                | URL of an image to show before the model loads.                                                            |
| `ar`               | `bool`                              | `True`                                     | Enables AR features and displays the AR button if supported.                                               |
| `arModes`          | `string`                            | `"webxr scene-viewer quick-look"`          | Space-separated list of preferred AR modes.                                                                |
| `arScale`          | `'auto'`, `'fixed'`                 | `'auto'`                                   | Controls model scaling in AR ('auto' adjusts, 'fixed' uses model's native scale).                          |
| `arButtonText`     | `string`                            | `'View in your space'`                     | Text displayed on the default AR button.                                                                   |
| `customArPrompt`   | `node` (string or Dash component)   | `null`                                     | Custom content to show while initializing AR (replaces default hand icon).                                 |
| `customArFailure`  | `node` (string or Dash component)   | `null`                                     | Custom content to show if AR fails to start or track (replaces default message).                           |
| `toneMapping`      | `'neutral'`, `'aces'`, ...         | `'neutral'`                                | Adjusts the color grading/tone mapping (see `<model-viewer>` docs).                                      |
| `shadowIntensity`  | `number` or `string`                | `0`                                        | Controls the opacity of the model's shadow.                                                                |
| `hotspots`         | `array`                             | `[]`                                       | List of hotspot objects (see structure below).                                                             |
| `variantName`      | `string`                            | `null`                                     | Selects a specific model variant if the GLTF file defines variants. Use `null` or `'default'` for default. |
| `setProps`         | `func`                              | (Dash Internal)                            | Callback function to update component properties.                                                          |
| `loading_state`    | `object`                            | (Dash Internal)                            | Object describing the loading state of the component or its props.                                         |

**Hotspot Object Structure:**

Each object in the `hotspots` array can have the following keys:

*   `slot`: (String, Required) A unique name for the hotspot's `slot` attribute (e.g., `"hotspot-1"`, `"hotspot-visor"`). Used for targeting with CSS.
*   `position`: (String, Required) The 3D coordinates `"X Y Z"` where the hotspot should be placed in model space.
*   `normal`: (String, Optional) The surface normal vector `"X Y Z"` at the position. Influences the hotspot's orientation relative to the surface.
*   `text`: (String, Optional) Text content to display *inside* the hotspot's `div` element.
*   `children_classname`: (String, Optional) A CSS class name to add to the hotspot's `div` element for custom styling.
*   `orbit`: (String, Optional) If provided, clicking this hotspot will internally update the model viewer's camera orbit to this value (e.g., `"45deg 60deg 2m"`). Used for [Camera Views via Hotspots](#camera-views-via-hotspots).
*   `target`: (String, Optional) If provided along with `orbit`, clicking this hotspot updates the camera target (e.g., `"0m 1m 0m"`).
*   `fov`: (String, Optional) If provided along with `orbit`/`target`, clicking updates the field of view (e.g., `"30deg"`). Defaults to `45deg` for camera view hotspots if not specified.

---

## Client-Side Scripting

For advanced interactions not built into the component (like drawing dimension lines or handling complex placement logic), you need to write JavaScript functions within your Dash app's `assets` folder.

1.  Create a JavaScript file in your `assets` directory (e.g., `assets/model_viewer_clientside.js`).
2.  Define your functions within a namespace, typically `window.dash_clientside.clientside.yourNamespace`.
3.  Use `dash.clientside_callback` in Python to trigger these functions.
4.  Your JavaScript functions can access the `<model-viewer>` element using its ID and utilize its extensive JavaScript API (e.g., `modelViewerElement.positionAndNormalFromPoint()`, `modelViewerElement.getBoundingBox()`, etc.). Refer to the [official <model-viewer> documentation](https://modelviewer.dev/docs/) for API details.

**Example JS Structure (`assets/model_viewer_clientside.js`):**

```javascript
window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.clientside = window.dash_clientside.clientside || {};

window.dash_clientside.clientside.modelViewer = { // Use a namespace like 'modelViewer'

    // Example for dynamic dimensions
    updateDimensions: function(modelSrc, showDims, units, hotspots, viewerId, containerId) {
        if (!window.dash_clientside.initial_callback_completed) { // Prevent execution before layout is ready
             window.dash_clientside.initial_callback_completed = true;
             // return window.dash_clientside.no_update; // Or handle initial state if needed
        }

        const modelViewerElement = document.getElementById(viewerId);
        const container = document.getElementById(containerId);
        if (!modelViewerElement || !container) {
            console.warn("Model viewer or container not found");
            return window.dash_clientside.no_update;
        }

        // --- Your Logic Here ---
        // 1. Check if dimensions should be shown (showDims)
        // 2. Wait for model to be loaded if necessary (modelViewerElement.loaded)
        // 3. Get model dimensions/bounding box using modelViewerElement API
        // 4. Calculate hotspot positions based on dimensions
        // 5. Update hotspot `data-position` attributes (if needed, though usually set by Python)
        // 6. Convert dimensions to selected units
        // 7. Update text content of dimension hotspots (`.dim`)
        // 8. Create/update SVG overlay within the container for lines
        // 9. Draw SVG lines between corresponding dot hotspots
        // 10. Make sure SVG/hotspots are visible/hidden based on showDims

        console.log(`Updating dimensions for ${viewerId}, Units: ${units}, Show: ${showDims}`);
        // ... Implementation ...

        return window.dash_clientside.no_update; // Indicate no Dash property needs updating from JS
    },

    // Example for interactive hotspot placement
    handleAddHotspotClick: function(n_clicks, viewerId, currentMode, labelText) {
         if (currentMode !== 'adding' || !n_clicks) { // Only proceed if in adding mode and clicked
             return window.dash_clientside.no_update;
         }

        const modelViewerElement = document.getElementById(viewerId);
        if (!modelViewerElement) {
            return window.dash_clientside.no_update;
        }

        // --- Your Logic Here ---
        // 1. Use modelViewerElement.positionAndNormalFromPoint(centerX, centerY)
        //    where centerX/Y are the coordinates of the reticle (usually center of viewer)
        // 2. This returns an object {position: Vector3, normal: Vector3} or null
        // 3. Format position/normal into strings ("X Y Z")
        // 4. Create a new hotspot data object:
        const newHotspotData = {
            // position: formattedPositionString,
            // normal: formattedNormalString,
            text: labelText || "New Hotspot",
            slot: `hotspot-${Date.now()}` // Generate unique slot
            // children_classname: "hotspot-dynamic" // Optional class
        };
        // 5. Return this data to trigger the server-side callback via Output('new-hotspot-data-store', 'data')
        console.log("Placing hotspot:", newHotspotData);
        // return newHotspotData; // Replace with actual data

        // Placeholder - replace with actual logic and return value
        alert(`Simulating placement for: ${labelText || 'New Hotspot'}`);
        return window.dash_clientside.no_update; // Or return hotspot data object
    }
};
```

*(See the advanced examples' Python files for how `clientside_callback` is configured)*

---

## Styling

Styling of the `<model-viewer>` element itself and its interactive elements (like hotspots) is primarily done through CSS.

1.  Create a CSS file in your `assets` folder (e.g., `assets/model_viewer_styles.css`). Dash automatically loads files from this folder.
2.  Use CSS selectors to target the component and its parts:
    *   Target the viewer by ID: `#your-viewer-id { ... }`
    *   Target all hotspots: `.hotspot { ... }`
    *   Target specific hotspots by slot: `.hotspot[slot='hotspot-visor'] { ... }`
    *   Target hotspots with specific classes: `.view-button { ... }`, `.dot { ... }`, `.dim { ... }`
    *   Style the default AR button: `#your-viewer-id button[slot='ar-button'] { ... }` (or just `button[slot='ar-button']` if unique)
    *   Style annotation text/boxes (often using pseudo-elements like `::after` on the hotspot).
    *   Style dimension lines (target the SVG elements added by your client-side script).
    *   Style the reticle for dynamic placement.

Refer to the CSS files accompanying the usage examples for specific implementations. The `<model-viewer>` documentation also provides guidance on styling its parts.

---

## Contributing

Contributions are welcome! Please feel free to submit Pull Requests or open Issues.

**Development Setup:**
*(Add instructions here for developers, e.g., cloning, installing dev dependencies, building the component, running tests)*

1.  Clone the repository.
2.  Install Python dependencies (`pip install -r requirements.txt`).
3.  Install JS dependencies (`npm install`).
4.  Build the component (`npm run build`).
5.  Run usage examples to test.

---

## License

This project is licensed under the Apache-2.0 License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgements

*   This component relies heavily on Google's excellent [`<model-viewer>` web component](https://modelviewer.dev/).
*   Built with the [Plotly Dash](https://dash.plotly.com/) framework.

