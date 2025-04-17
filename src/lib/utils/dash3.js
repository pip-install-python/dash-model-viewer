/**
 * Utility functions to support both Dash 2 and Dash 3 components
 */

import React from "react";

/**
 * Check if running in Dash 3 environment
 * @returns {boolean}
 */
export const isDash3 = () => {
  return !!(typeof window !== 'undefined' && 'dash_component_api' in window);
};

/**
 * Set persistence properties for a component
 * Ensures compatibility between React < 18.3 (Dash 2 defaultProps) and React 18.3+ (Dash 3 dashPersistence)
 * @param {React.ComponentType} Component - The component class or function
 * @param {string[]} [props=["value"]] - Array of prop names to persist
 */
export const setPersistence = (Component, props = ["value"]) => {
  const persistence = { persisted_props: props, persistence_type: "local" };

  // Check React version (Dash 3 uses React 18.3+)
  // Note: This React version check might not be perfectly aligned with Dash versions in edge cases,
  // but it's the pattern suggested in the migration guide. A more robust check might involve
  // checking for window.dash_component_api existence if possible *outside* React render cycle.
  // However, this setup needs to happen at the module level before rendering.
  if (typeof React.version === 'string' && parseFloat(React.version) < 18.3) {
    Component.defaultProps = {
      ...Component.defaultProps, // Preserve existing defaultProps if any
      ...persistence
    };
  } else {
    Component.dashPersistence = persistence;
  }
};


/**
 * Get loading state, compatible with Dash 2 (props) and Dash 3 (context hook)
 * IMPORTANT: This hook-based version can ONLY be called inside a React Function Component body.
 * @param {object | undefined} loading_state - The loading_state prop passed by Dash
 * @returns {boolean} - True if the component is loading, false otherwise.
 */
export const useLoadingState = (loading_state) => {
  if (isDash3() && typeof window !== 'undefined' && window.dash_component_api) {
    try {
      // Attempt to use the Dash 3 hook
      const ctx = window.dash_component_api.useDashContext();
      return ctx.useLoading();
    } catch (e) {
      // This might happen if called outside a function component context or during SSR
      // Fallback to props for safety, although useLoading should ideally work.
      console.error("Dash 3 useLoading hook failed, falling back to props:", e);
      return loading_state?.is_loading ?? false;
    }
  }
  // Fallback for Dash 2 or if Dash 3 API fails
  return loading_state?.is_loading ?? false;
};


/**
 * Get component layout info, works with both Dash 2 (_dashprivate_layout) and 3 (getLayout)
 * @param {object} child - A React child element potentially containing Dash layout info.
 * @returns {{ type: any; props: any }} - The type and props from the layout.
 */
export const getChildLayout = (child) => {
  if (!child || !child.props) {
    return { type: null, props: {} };
  }

  if (isDash3() && typeof window !== 'undefined' && window.dash_component_api && child.props.componentPath) {
      try {
        // Use Dash 3 API
        const layout = window.dash_component_api.getLayout(child.props.componentPath);
        // Ensure layout is an object, handle potential errors or unexpected returns
        if (layout && typeof layout === 'object') {
            return { type: layout.type, props: layout.props || {} };
        }
        console.warn("Dash 3 getLayout returned unexpected value:", layout);
        return { type: null, props: {} };
      } catch (e) {
        console.error("Dash 3 getLayout failed:", e);
        return { type: null, props: {} }; // Fallback on error
      }
  } else if (child.props._dashprivate_layout) {
      // Use Dash 2 fallback
      return {
        type: child.props._dashprivate_layout.type,
        props: child.props._dashprivate_layout.props || {}, // Ensure props is an object
      };
  }

  // Default if neither method is applicable
  return { type: null, props: {} };
};

/**
 * Get child props from layout using getChildLayout
 * @param {object} child - A React child element.
 * @returns {any} - The props object from the child's layout.
 */
export const getChildProps = (child) => {
  return getChildLayout(child).props;
};


/**
 * Set component props using Dash 3's path-based set_props if available.
 * Note: This is generally for updating *other* components. For self-updates, use the `setProps` prop.
 * @param {string} componentPathOrId - The component path (Dash 3) or ID.
 * @param {Record<string, any>} props - The props object to set.
 */
export const setComponentProps = (componentPathOrId, props) => {
   // Check for Dash 3 API first, as it accepts paths
  if (isDash3() && typeof window !== 'undefined' && window.dash_clientside) {
    try {
        window.dash_clientside.set_props(componentPathOrId, props);
        return;
    } catch (e) {
        console.error("Dash 3 set_props failed:", e);
        // Potentially fallback if needed, though the API might just not exist
    }
  }
  // Fallback or alternative for non-Dash 3 environments or if the above fails:
  // If componentPathOrId is likely just an ID (doesn't look like a path string),
  // you might still try dash_clientside.set_props if it exists,
  // otherwise, there isn't a direct equivalent in Dash 2 from the client-side like this.
  // console.warn("setComponentProps: Dash 3 API not available or failed. Ensure componentPathOrId is an ID for potential Dash 2 compatibility if dash_clientside exists.");
  // if (typeof window !== 'undefined' && window.dash_clientside) {
  //    window.dash_clientside.set_props(componentPathOrId, props); // Might work if it's just an ID
  // }
};


// --- Hooks for Store/Dispatch (Dash 3+ only) ---
// These hooks MUST be called within Function Component bodies.

/**
 * Use Dash 3 store if available. Returns null otherwise.
 * @returns {any | null}
 */
export const useDashStore = () => {
  if (isDash3() && typeof window !== 'undefined' && window.dash_component_api) {
    try {
      return window.dash_component_api.useDashContext().useStore();
    } catch (e) {
      console.error("Dash 3 useStore hook failed:", e);
      return null;
    }
  }
  return null;
};

/**
 * Use Dash 3 dispatch if available. Returns null otherwise.
 * @returns {Function | null}
 */
export const useDashDispatch = () => {
  if (isDash3() && typeof window !== 'undefined' && window.dash_component_api) {
    try {
      return window.dash_component_api.useDashContext().useDispatch();
    } catch (e) {
      console.error("Dash 3 useDispatch hook failed:", e);
      return null;
    }
  }
  return null;
};