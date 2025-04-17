// assets/model_viewer_clientside.js

const _modelViewerLogic = {

  svgElements: {},

  // Add 'hotspotsProp' as an argument (we don't actually use its value, but need it for the Input)
  _updateDimensionsImpl: function(newSrc, checkboxValue, selectedUnit, hotspotsProp, modelViewerId, containerId) {
    const modelViewer = document.getElementById(modelViewerId);
    const container = document.getElementById(containerId);
    const show = checkboxValue.includes('show');
    // console.log(`Clientside Update. Show=${show}, Unit=${selectedUnit}`); // Debug

    if (!modelViewer || !container) { /* Error check */ return window.dash_clientside.no_update; }

    // --- Get or Create SVG ---
    let svg = this.svgElements[modelViewerId]?.svg;
    let dimLines = this.svgElements[modelViewerId]?.lines;
    const svgNs = 'http://www.w3.org/2000/svg';
    if (!svg) { /* Create SVG/Lines */
      // console.log("Creating SVG elements"); // Debug
      svg = document.createElementNS(svgNs, 'svg'); /* ... attributes ... */
      svg.setAttribute('id', `${modelViewerId}-svg`);
      svg.setAttribute('width', '100%'); svg.setAttribute('height', '100%');
      Object.assign(svg.style, { position: 'absolute', top: '0', left: '0', pointerEvents: 'none', display: 'block' });
      dimLines = [];
      for (let i = 0; i < 5; i++) { /* create lines */
          const line = document.createElementNS(svgNs, 'line'); line.setAttribute('class', 'dimensionLine');
          line.setAttribute('x1','0'); line.setAttribute('y1','0'); line.setAttribute('x2','0'); line.setAttribute('y2','0');
          svg.appendChild(line); dimLines.push(line);
      }
      container.appendChild(svg); this.svgElements[modelViewerId] = { svg: svg, lines: dimLines };
    }

    // --- Helper Functions ---

    // UPDATE HOTSPOT: Sets position and text ONLY. NO visibility logic.
    const updateHotspot = (name, position, text) => {
        // Query within the model-viewer element using the slot
        const hotspot = modelViewer.querySelector(`div.hotspot[slot="${name}"]`);
        if (hotspot) { // Check if hotspot element currently exists in DOM
            if (modelViewer.updateHotspot) { try { modelViewer.updateHotspot({ name: name, position: position }); } catch(e) { hotspot.setAttribute('data-position', position); } }
            else { hotspot.setAttribute('data-position', position); }
            hotspot.textContent = text || '';
        } // If hotspot doesn't exist (because server removed it), do nothing.
    };

    // DRAW LINE: Handles coordinates AND line visibility based on 'show'.
    const drawLine = (svgLine, dot1Name, dot2Name, dimName) => {
        // Important: Only query hotspots if 'show' is true, otherwise points might be gone
        const dot1 = show ? modelViewer.queryHotspot(dot1Name) : null;
        const dot2 = show ? modelViewer.queryHotspot(dot2Name) : null;
        const dimHotspot = show && dimName ? modelViewer.queryHotspot(dimName) : null;

        if (svgLine && dot1?.canvasPosition && dot2?.canvasPosition) {
            svgLine.setAttribute('x1', dot1.canvasPosition.x); svgLine.setAttribute('y1', dot1.canvasPosition.y);
            svgLine.setAttribute('x2', dot2.canvasPosition.x); svgLine.setAttribute('y2', dot2.canvasPosition.y);
            const facingCamera = !dimHotspot || dimHotspot.facingCamera;
            // Line visibility depends on show flag AND facingCamera
            if (show && facingCamera) {
                svgLine.classList.remove('hide');
            } else {
                svgLine.classList.add('hide'); // Hide if !show or not facing
            }
        } else {
            if(svgLine) svgLine.classList.add('hide'); // Hide if points not ready/found
        }
    };

    // RENDER SVG: Calls drawLine.
    const renderSVG = () => {
        if (!modelViewer.loaded || !dimLines) return;
        // console.log("Rendering SVG..."); // Debug
        try { /* Draw lines */
             drawLine(dimLines[0], 'hotspot-dot+X-Y+Z', 'hotspot-dot+X-Y-Z', 'hotspot-dim+X-Y');
             drawLine(dimLines[1], 'hotspot-dot+X-Y-Z', 'hotspot-dot+X+Y-Z', 'hotspot-dim+X-Z');
             drawLine(dimLines[2], 'hotspot-dot+X+Y-Z', 'hotspot-dot-X+Y-Z', null);
             drawLine(dimLines[3], 'hotspot-dot-X+Y-Z', 'hotspot-dot-X-Y-Z', 'hotspot-dim-X-Z');
             drawLine(dimLines[4], 'hotspot-dot-X-Y-Z', 'hotspot-dot-X-Y+Z', 'hotspot-dim-X-Y');
        } catch (error) { console.error("Error rendering SVG:", error); }
    };

    // CALCULATE DIMENSIONS: Gets size/center, converts units, calls updateHotspot (pos/text only).
    const calculateAndUpdateDimensions = () => {
        if (!modelViewer.loaded) return;
        // console.log(`Calculating dimensions. Unit: ${selectedUnit}`); // Debug
        // Check if hotspots actually exist before trying to calculate
        const firstHotspot = modelViewer.querySelector(`div.hotspot[slot="hotspot-dot+X-Y+Z"]`);
        if (!firstHotspot && show) {
            // console.warn("calculateAndUpdateDimensions called when show=true, but hotspots not found in DOM yet. Retrying shortly."); // Debug
            // Hotspots might not be rendered yet by React after server update. Retry.
            setTimeout(calculateAndUpdateDimensions, 50);
            return;
        }
        if (!show) {
            // console.log("calculateAndUpdateDimensions called when show=false. Skipping calculation."); // Debug
            // If not showing, don't calculate, just ensure lines are hidden via renderSVG later
            renderSVG(); // Ensure lines are hidden based on 'show' = false
            return;
        }

        try {
            const center = modelViewer.getBoundingBoxCenter(); const size = modelViewer.getDimensions();
            if (!size || !center) { console.warn("Cannot get dimensions/center."); return; }
            const x2 = size.x/2, y2 = size.y/2, z2 = size.z/2;

            // --- MODIFIED: Added 'm' case ---
            let factor = 100, unitLabel = 'cm', precision = 0; // Default to cm
            if (selectedUnit === 'mm') { factor = 1000; unitLabel = 'mm'; precision = 0;}
            else if (selectedUnit === 'm') { factor = 1; unitLabel = 'm'; precision = 2; } // Added meters (factor=1, 2 decimals)
            else if (selectedUnit === 'in') { factor = 39.3701; unitLabel = 'in'; precision = 1;}
            else if (selectedUnit === 'ft') { factor = 3.28084; unitLabel = 'ft'; precision = 2;}
            // --- END MODIFICATION ---

            // Update hotspot positions/text ONLY
            // Note: Position values (e.g., center.x + x2) are always in meters internally
            updateHotspot('hotspot-dot+X-Y+Z', `${center.x + x2} ${center.y - y2} ${center.z + z2}`);
            // Note: Dimension text uses the calculated factor, unitLabel, and precision
            updateHotspot('hotspot-dim+X-Y', `${center.x + x2*1.2} ${center.y - y2*1.1} ${center.z}`, `${(size.z * factor).toFixed(precision)} ${unitLabel}`);
            updateHotspot('hotspot-dot+X-Y-Z', `${center.x + x2} ${center.y - y2} ${center.z - z2}`);
            updateHotspot('hotspot-dim+X-Z', `${center.x + x2 * 1.2} ${center.y} ${center.z - z2 * 1.2}`, `${(size.y * factor).toFixed(precision)} ${unitLabel}`);
            updateHotspot('hotspot-dot+X+Y-Z', `${center.x + x2} ${center.y + y2} ${center.z - z2}`);
            updateHotspot('hotspot-dim+Y-Z', `${center.x} ${center.y + y2 * 1.1} ${center.z - z2 * 1.1}`, `${(size.x * factor).toFixed(precision)} ${unitLabel}`);
            updateHotspot('hotspot-dot-X+Y-Z', `${center.x - x2} ${center.y + y2} ${center.z - z2}`);
            updateHotspot('hotspot-dim-X-Z', `${center.x - x2 * 1.2} ${center.y} ${center.z - z2 * 1.2}`, `${(size.y * factor).toFixed(precision)} ${unitLabel}`);
            updateHotspot('hotspot-dot-X-Y-Z', `${center.x - x2} ${center.y - y2} ${center.z - z2}`);
            updateHotspot('hotspot-dim-X-Y', `${center.x - x2 * 1.2} ${center.y - y2 * 1.1} ${center.z}`, `${(size.z * factor).toFixed(precision)} ${unitLabel}`);
            updateHotspot('hotspot-dot-X-Y+Z', `${center.x - x2} ${center.y - y2} ${center.z + z2}`);


            // Render SVG lines AFTER data is set
            renderSVG();
        } catch (error) { console.error("Error calculating dimensions:", error); }
    };

    // --- Event Listener Setup ---
    if (!modelViewer.dimensionListenersAttached) {
        const loadHandler = () => { /*console.log("Load event triggered"); */ calculateAndUpdateDimensions(); }
        const cameraChangeHandler = () => { /*console.log("Camera change triggered"); */ renderSVG(); }
        modelViewer.addEventListener('load', loadHandler);
        modelViewer.addEventListener('camera-change', cameraChangeHandler);
        modelViewer.dimensionListenersAttached = true;
        modelViewer._dimensionLoadHandler = loadHandler;
        modelViewer._dimensionCameraChangeHandler = cameraChangeHandler;
        if (modelViewer.loaded) { /*console.log("Already loaded on attach");*/ setTimeout(calculateAndUpdateDimensions, 50); }
    }

    // --- Final Visibility Control (SVG Only) & Trigger Calculation ---
    if (svg) { // Check if SVG exists
        if (show) {
            // console.log("Final Block: Setting SVG visible."); // Debug
            svg.classList.remove('hide');
            // Ensure calculations run if model is loaded, as hotspots were just added by React
            if (modelViewer.loaded) {
                 setTimeout(calculateAndUpdateDimensions, 50); // Recalculate slightly deferred
            }
        } else {
            // console.log("Final Block: Setting SVG hidden."); // Debug
            svg.classList.add('hide');
            // Ensure lines are hidden immediately based on the new 'show' state
            renderSVG();
        }
    }

    return window.dash_clientside.no_update;
  }
};

// --- Wrapper Function ---
window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.modelViewer = {
    // Update arguments to include hotspotsProp
    updateDimensions: function(newSrc, checkboxValue, selectedUnit, hotspotsProp, modelViewerId, containerId) {
        if (window._modelViewerLogic?._updateDimensionsImpl) {
            // Pass all arguments through
            return window._modelViewerLogic._updateDimensionsImpl(newSrc, checkboxValue, selectedUnit, hotspotsProp, modelViewerId, containerId);
        } else {
            console.warn("modelViewer logic not ready, retrying...");
            setTimeout(() => {
                if (window.dash_clientside.modelViewer?.updateDimensions) {
                    // Pass all arguments in the retry
                    window.dash_clientside.modelViewer.updateDimensions(newSrc, checkboxValue, selectedUnit, hotspotsProp, modelViewerId, containerId);
                }
            }, 100);
            return window.dash_clientside.no_update;
        }
    }
};

// Assign logic object AFTER definition
window._modelViewerLogic = _modelViewerLogic;