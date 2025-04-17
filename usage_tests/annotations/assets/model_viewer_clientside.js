// assets/model_viewer_clientside.js

window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.modelViewer = window.dash_clientside.modelViewer || {};

window.dash_clientside.modelViewer.handleAddHotspotClick = function(n_clicks, modelViewerId, currentMode, labelText) {

    if (currentMode !== 'adding') {
        return window.dash_clientside.no_update;
    }
    if (!labelText || labelText.trim() === '') {
        alert("Please enter a label for the hotspot.");
        return window.dash_clientside.no_update;
    }

    const modelViewer = document.getElementById(modelViewerId);
    if (!modelViewer) {
        console.error("[Clientside] Model viewer element not found:", modelViewerId);
        alert("Error: Could not find model viewer element.");
        return window.dash_clientside.no_update;
    }

    if (typeof modelViewer.positionAndNormalFromPoint !== 'function') {
        console.error("[Clientside] modelViewer.positionAndNormalFromPoint method is not available.");
        alert("Error: Required model-viewer method not found.");
        return window.dash_clientside.no_update;
    }

    const viewerRect = modelViewer.getBoundingClientRect();
    const centerClientX = viewerRect.left + viewerRect.width / 2;
    const centerClientY = viewerRect.top + viewerRect.height / 2;

    let positionAndNormal = null;
    try {
        positionAndNormal = modelViewer.positionAndNormalFromPoint(centerClientX, centerClientY);
    } catch (e) {
        console.error("[Clientside] Error calling positionAndNormalFromPoint:", e);
        alert("Error occurred while trying to find the position on the model.");
        return window.dash_clientside.no_update;
    }

    if (positionAndNormal === null) {
        alert("Could not place hotspot. Point the center reticle directly at the model surface.");
        return window.dash_clientside.no_update;
    }

    const { position, normal } = positionAndNormal;
    const newPositionStr = `${position.x.toFixed(4)} ${position.y.toFixed(4)} ${position.z.toFixed(4)}`;
    const newNormalStr = normal ? `${normal.x.toFixed(4)} ${normal.y.toFixed(4)} ${normal.z.toFixed(4)}` : "0 0 1";
    const newSlot = `hotspot-dynamic-${Date.now()}`;

    const newHotspot = {
        slot: newSlot,
        position: newPositionStr,
        normal: newNormalStr,
        text: labelText.trim(),
        children_classname: "hotspot-dynamic"
    };

    return newHotspot;
};

console.log("model_viewer_clientside.js loaded: handleAddHotspotClick defined (v2).");