# AUTO GENERATED FILE - DO NOT EDIT

export dashmodelviewer

"""
    dashmodelviewer(;kwargs...)

A DashModelViewer component.

Keyword arguments:
- `id` (String; required): Component ID
- `alt` (String; required): Alt text for accessibility
- `ar` (Bool; optional): Enable AR features
- `arButtonText` (String; optional): Text for the default AR button
- `arModes` (String; optional)
- `arScale` (a value equal to: 'auto', 'fixed'; optional)
- `cameraControls` (Bool; optional): Enable camera controls
- `cameraOrbit` (String; optional): Initial camera orbital position (\$theta \$phi \$radius)
- `cameraTarget` (String; optional): Initial camera target point (\$X \$Y \$Z)
- `customArFailure` (String | a list of or a singular dash component, string or number; optional): Custom React element for the AR failure message
- `customArPrompt` (String | a list of or a singular dash component, string or number; optional): Custom React element for the AR prompt
- `fieldOfView` (String; optional): Camera field of view
- `hotspots` (optional): Array of hotspot objects passed from the server. hotspots has the following type: Array of lists containing elements 'slot', 'position', 'normal', 'orbit', 'target', 'fov', 'text', 'children_classname'.
Those elements have the following types:
  - `slot` (String; optional)
  - `position` (String; optional)
  - `normal` (String; optional)
  - `orbit` (String; optional)
  - `target` (String; optional)
  - `fov` (String; optional)
  - `text` (String; optional)
  - `children_classname` (String; optional)s
- `interpolationDecay` (Real | String; optional): Camera interpolation decay rate
- `loading_state` (optional): Object that holds the loading state object coming from dash-renderer. loading_state has the following type: lists containing elements 'is_loading', 'prop_name', 'component_name'.
Those elements have the following types:
  - `is_loading` (Bool; optional): Determines if the component is loading or not
  - `prop_name` (String; optional): Holds which property is loading
  - `component_name` (String; optional): Holds the name of the component that is loading
- `maxCameraOrbit` (String; optional): Maximum camera orbit bounds
- `maxFieldOfView` (String; optional): Maximum camera field of view
- `minCameraOrbit` (String; optional): Minimum camera orbit bounds
- `minFieldOfView` (String; optional): Minimum camera field of view
- `poster` (String; optional): Poster image URL
- `shadowIntensity` (Real | String; optional)
- `src` (String; required): Model source URL (.glb or .gltf)
- `style` (Dict; optional): CSS Style object
- `toneMapping` (a value equal to: 'neutral', 'aces', 'agx', 'reinhard', 'cineon', 'linear', 'none'; optional)
- `touchAction` (a value equal to: 'pan-y', 'pan-x', 'none'; optional): Touch action behavior
- `variantName` (String; optional)
"""
function dashmodelviewer(; kwargs...)
        available_props = Symbol[:id, :alt, :ar, :arButtonText, :arModes, :arScale, :cameraControls, :cameraOrbit, :cameraTarget, :customArFailure, :customArPrompt, :fieldOfView, :hotspots, :interpolationDecay, :loading_state, :maxCameraOrbit, :maxFieldOfView, :minCameraOrbit, :minFieldOfView, :poster, :shadowIntensity, :src, :style, :toneMapping, :touchAction, :variantName]
        wild_props = Symbol[]
        return Component("dashmodelviewer", "DashModelViewer", "dash_model_viewer", available_props, wild_props; kwargs...)
end

