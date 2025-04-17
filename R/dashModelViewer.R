# AUTO GENERATED FILE - DO NOT EDIT

#' @export
dashModelViewer <- function(id=NULL, alt=NULL, ar=NULL, arButtonText=NULL, arModes=NULL, arScale=NULL, cameraControls=NULL, cameraOrbit=NULL, cameraTarget=NULL, customArFailure=NULL, customArPrompt=NULL, fieldOfView=NULL, hotspots=NULL, interpolationDecay=NULL, loading_state=NULL, maxCameraOrbit=NULL, maxFieldOfView=NULL, minCameraOrbit=NULL, minFieldOfView=NULL, poster=NULL, shadowIntensity=NULL, src=NULL, style=NULL, toneMapping=NULL, touchAction=NULL, variantName=NULL) {
    
    props <- list(id=id, alt=alt, ar=ar, arButtonText=arButtonText, arModes=arModes, arScale=arScale, cameraControls=cameraControls, cameraOrbit=cameraOrbit, cameraTarget=cameraTarget, customArFailure=customArFailure, customArPrompt=customArPrompt, fieldOfView=fieldOfView, hotspots=hotspots, interpolationDecay=interpolationDecay, loading_state=loading_state, maxCameraOrbit=maxCameraOrbit, maxFieldOfView=maxFieldOfView, minCameraOrbit=minCameraOrbit, minFieldOfView=minFieldOfView, poster=poster, shadowIntensity=shadowIntensity, src=src, style=style, toneMapping=toneMapping, touchAction=touchAction, variantName=variantName)
    if (length(props) > 0) {
        props <- props[!vapply(props, is.null, logical(1))]
    }
    component <- list(
        props = props,
        type = 'DashModelViewer',
        namespace = 'dash_model_viewer',
        propNames = c('id', 'alt', 'ar', 'arButtonText', 'arModes', 'arScale', 'cameraControls', 'cameraOrbit', 'cameraTarget', 'customArFailure', 'customArPrompt', 'fieldOfView', 'hotspots', 'interpolationDecay', 'loading_state', 'maxCameraOrbit', 'maxFieldOfView', 'minCameraOrbit', 'minFieldOfView', 'poster', 'shadowIntensity', 'src', 'style', 'toneMapping', 'touchAction', 'variantName'),
        package = 'dashModelViewer'
        )

    structure(component, class = c('dash_component', 'list'))
}
