/**
 * dash-model-viewer — Dash <-> <model-viewer> shim.
 *
 * HAND-AUTHORED. There is no build step, no webpack, no babel and no
 * dash-generate-components in this package. This file is the source; edit it
 * directly. See .claude/ARCHITECTURE.md.
 *
 * Deliberately ES5, dependency-free, and IIFE-wrapped: it must run as a
 * classic script in document order, before Dash instantiates its renderer.
 * Do not add `type="module"`, `async` or `defer` to the resource entry that
 * emits this file — any of them defers execution past `new DashRenderer(...)`
 * and reintroduces the custom-element timing race.
 */
(function () {
    "use strict";

    var React = window.React;
    if (!React) {
        // Should be impossible: Dash emits React before any component suite.
        console.error("[dash_model_viewer] window.React is not available.");
        return;
    }

    var DEFAULT_CAMERA_DEBOUNCE = 100;

    /* ---------------------------------------------------------------- *
     * Attribute mapping
     * ---------------------------------------------------------------- */

    /* snake_case Python prop -> kebab-case model-viewer attribute. */
    var NAMED_ATTRS = {
        src: "src",
        alt: "alt",
        camera_controls: "camera-controls",
        touch_action: "touch-action",
        camera_orbit: "camera-orbit",
        camera_target: "camera-target",
        field_of_view: "field-of-view",
        min_field_of_view: "min-field-of-view",
        max_field_of_view: "max-field-of-view",
        min_camera_orbit: "min-camera-orbit",
        max_camera_orbit: "max-camera-orbit",
        interpolation_decay: "interpolation-decay",
        poster: "poster",
        ar: "ar",
        ar_modes: "ar-modes",
        ar_scale: "ar-scale",
        tone_mapping: "tone-mapping",
        shadow_intensity: "shadow-intensity",
        variant_name: "variant-name"
    };

    /* Attributes whose meaning is presence, not value. */
    var BOOLEAN_ATTRS = {"camera-controls": true, "ar": true};

    function kebab(s) {
        return s.replace(/_/g, "-");
    }

    function has(o, k) {
        return Object.prototype.hasOwnProperty.call(o, k);
    }

    /**
     * Build the full attribute set for one render.
     *
     * Precedence, lowest to highest — asserted by tests/test_components.py:
     *   `attributes` dict  <  `mv_*` wildcards  <  named props
     */
    function computeAttributes(props) {
        var out = {};
        var k;

        if (props.attributes) {
            for (k in props.attributes) {
                if (has(props.attributes, k)) {
                    out[k] = props.attributes[k];
                }
            }
        }

        for (k in props) {
            if (has(props, k) && k.indexOf("mv_") === 0 && props[k] != null) {
                out[kebab(k.slice(3))] = props[k];
            }
        }

        for (k in NAMED_ATTRS) {
            if (!has(NAMED_ATTRS, k)) {
                continue;
            }
            var v = props[k];
            if (v === undefined || v === null) {
                continue;
            }
            /* `variant_name="default"` means "the GLTF default", which
               model-viewer expresses as the attribute being absent. */
            if (k === "variant_name" && v === "default") {
                continue;
            }
            out[NAMED_ATTRS[k]] = v;
        }

        return out;
    }

    /* Apply `next` to the element, removing anything that has gone away.
       Diffed against the previous applied set so we never thrash attributes
       model-viewer is mid-animation on. */
    function applyAttributes(el, next, prevRef) {
        var prev = prevRef.current || {};
        var key;

        for (key in prev) {
            if (has(prev, key) && !has(next, key)) {
                el.removeAttribute(key);
            }
        }

        for (key in next) {
            if (!has(next, key)) {
                continue;
            }
            var value = next[key];

            if (BOOLEAN_ATTRS[key]) {
                if (value) {
                    if (!el.hasAttribute(key)) {
                        el.setAttribute(key, "");
                    }
                } else {
                    el.removeAttribute(key);
                }
                continue;
            }

            if (value === false || value === null || value === undefined) {
                el.removeAttribute(key);
                continue;
            }

            var str = String(value);
            if (el.getAttribute(key) !== str) {
                el.setAttribute(key, str);
            }
        }

        prevRef.current = next;
    }

    /* ---------------------------------------------------------------- *
     * Reading camera state back out
     * ---------------------------------------------------------------- */

    function str(value) {
        return value == null ? null : String(value);
    }

    function readCamera(el) {
        var camera = {};
        try {
            camera.orbit = str(el.getCameraOrbit && el.getCameraOrbit());
            camera.target = str(el.getCameraTarget && el.getCameraTarget());
            var fov = el.getFieldOfView && el.getFieldOfView();
            camera.field_of_view = fov == null ? null : fov + "deg";
        } catch (e) {
            /* The element can be queried before its scene is ready; a partial
               reading is better than throwing inside an event handler. */
        }
        return camera;
    }

    function readModelInfo(el) {
        var info = {dimensions: null, variants: [], animations: []};
        try {
            var d = el.getDimensions && el.getDimensions();
            if (d) {
                info.dimensions = {x: d.x, y: d.y, z: d.z};
            }
            info.variants = (el.availableVariants || []).slice();
            info.animations = (el.availableAnimations || []).slice();
        } catch (e) {
            /* same rationale as readCamera */
        }
        return info;
    }

    /* ---------------------------------------------------------------- *
     * ModelViewer
     * ---------------------------------------------------------------- */

    function ModelViewer(props) {
        var elRef = React.useRef(null);
        var appliedRef = React.useRef(null);
        /* Latest props, readable from listeners registered once on mount.
           This is what the 0.0.1 component got wrong: it closed over props at
           registration time and then tried to removeEventListener a *different*
           closure, so listeners accumulated for the life of the page. */
        var propsRef = React.useRef(props);
        propsRef.current = props;

        React.useEffect(function () {
            if (elRef.current) {
                applyAttributes(elRef.current, computeAttributes(props), appliedRef);
            }
        });

        React.useEffect(function () {
            var el = elRef.current;
            if (!el) {
                return undefined;
            }

            var cameraTimer = null;

            function setProps(update) {
                var fn = propsRef.current.setProps;
                if (fn) {
                    fn(update);
                }
            }

            function onCameraChange(event) {
                var source = event && event.detail && event.detail.source;
                /* Echo suppression. Without this, a callback that writes
                   camera_orbit triggers camera-change, which writes `camera`,
                   which re-triggers the callback — forever. */
                if (source !== "user-interaction") {
                    return;
                }
                var wait = propsRef.current.camera_change_debounce;
                if (wait == null) {
                    wait = DEFAULT_CAMERA_DEBOUNCE;
                }

                function emit() {
                    cameraTimer = null;
                    var camera = readCamera(el);
                    camera.source = source;
                    setProps({camera: camera});
                }

                if (cameraTimer) {
                    clearTimeout(cameraTimer);
                    cameraTimer = null;
                }
                if (wait > 0) {
                    cameraTimer = setTimeout(emit, wait);
                } else {
                    emit();
                }
            }

            function onLoad() {
                setProps({
                    model_state: {status: "loaded", progress: 1},
                    model_info: readModelInfo(el)
                });
            }

            function onError(event) {
                setProps({
                    model_state: {
                        status: "error",
                        progress: 0,
                        detail: str(event && event.detail && event.detail.type)
                    }
                });
            }

            function onProgress(event) {
                var pct = event && event.detail ? event.detail.totalProgress : 0;
                if (pct >= 1) {
                    /* `load` reports completion; a duplicate here would double
                       every callback at the end of every model load. */
                    return;
                }
                setProps({model_state: {status: "loading", progress: pct}});
            }

            function onArStatus(event) {
                setProps({ar_status: str(event && event.detail && event.detail.status)});
            }

            function onArTracking(event) {
                setProps({ar_tracking: str(event && event.detail && event.detail.status)});
            }

            function onClick(event) {
                if (!propsRef.current.pick_on_click) {
                    return;
                }
                try {
                    var hit = el.positionAndNormalFromPoint(event.clientX, event.clientY);
                    setProps({
                        scene_point: hit
                            ? {
                                position: str(hit.position),
                                normal: str(hit.normal),
                                uv: hit.uv ? [hit.uv.u, hit.uv.v] : null
                            }
                            : null
                    });
                } catch (e) {
                    setProps({scene_point: null});
                }
            }

            el.addEventListener("camera-change", onCameraChange);
            el.addEventListener("load", onLoad);
            el.addEventListener("error", onError);
            el.addEventListener("progress", onProgress);
            el.addEventListener("ar-status", onArStatus);
            el.addEventListener("ar-tracking", onArTracking);
            el.addEventListener("click", onClick);

            return function cleanup() {
                if (cameraTimer) {
                    clearTimeout(cameraTimer);
                }
                /* Same function identities that were added — this is the part
                   that actually removes them. */
                el.removeEventListener("camera-change", onCameraChange);
                el.removeEventListener("load", onLoad);
                el.removeEventListener("error", onError);
                el.removeEventListener("progress", onProgress);
                el.removeEventListener("ar-status", onArStatus);
                el.removeEventListener("ar-tracking", onArTracking);
                el.removeEventListener("click", onClick);
            };
        }, []);

        /* Only structural props go through React; everything else is applied
           imperatively above, so React never fights model-viewer over an
           attribute it is animating. */
        return React.createElement(
            "model-viewer",
            {
                ref: elRef,
                id: props.id,
                className: props.class_name,
                style: props.style
            },
            props.children
        );
    }

    /* ---------------------------------------------------------------- *
     * Slot
     * ---------------------------------------------------------------- */

    function Slot(props) {
        var className = props.class_name
            ? "dmv-slot " + props.class_name
            : "dmv-slot";

        function onClick() {
            if (props.setProps) {
                props.setProps({n_clicks: (props.n_clicks || 0) + 1});
            }
        }

        return React.createElement(
            "div",
            {
                id: props.id,
                slot: props.slot,
                className: className,
                style: props.style,
                "data-position": props.position,
                "data-normal": props.normal,
                onClick: onClick
            },
            props.children
        );
    }

    window.dash_model_viewer = {ModelViewer: ModelViewer, Slot: Slot};
})();
