% Auto-generated: do not edit by hand
\name{dashModelViewer}

\alias{dashModelViewer}

\title{DashModelViewer component}

\description{

}

\usage{
dashModelViewer(id=NULL, alt=NULL, ar=NULL, arButtonText=NULL, arModes=NULL,
arScale=NULL, cameraControls=NULL, cameraOrbit=NULL,
cameraTarget=NULL, customArFailure=NULL,
customArPrompt=NULL, fieldOfView=NULL, hotspots=NULL,
interpolationDecay=NULL, loading_state=NULL,
maxCameraOrbit=NULL, maxFieldOfView=NULL,
minCameraOrbit=NULL, minFieldOfView=NULL, poster=NULL,
shadowIntensity=NULL, src=NULL, style=NULL,
toneMapping=NULL, touchAction=NULL, variantName=NULL)
}

\arguments{
\item{id}{Character. Component ID}

\item{alt}{Character. Alt text for accessibility}

\item{ar}{Logical. Enable AR features}

\item{arButtonText}{Character. Text for the default AR button}

\item{arModes}{Character. }

\item{arScale}{A value equal to: 'auto', 'fixed'. }

\item{cameraControls}{Logical. Enable camera controls}

\item{cameraOrbit}{Character. Initial camera orbital position ($theta $phi $radius)}

\item{cameraTarget}{Character. Initial camera target point ($X $Y $Z)}

\item{customArFailure}{Character | a list of or a singular dash component, string or number. Custom React element for the AR failure message}

\item{customArPrompt}{Character | a list of or a singular dash component, string or number. Custom React element for the AR prompt}

\item{fieldOfView}{Character. Camera field of view}

\item{hotspots}{List of lists containing elements 'slot', 'position', 'normal', 'orbit', 'target', 'fov', 'text', 'children_classname'.
those elements have the following types:
  - slot (character; optional)
  - position (character; optional)
  - normal (character; optional)
  - orbit (character; optional)
  - target (character; optional)
  - fov (character; optional)
  - text (character; optional)
  - children_classname (character; optional)s. Array of hotspot objects passed from the server}

\item{interpolationDecay}{Numeric | character. Camera interpolation decay rate}

\item{loading_state}{Lists containing elements 'is_loading', 'prop_name', 'component_name'.
those elements have the following types:
  - is_loading (logical; optional): determines if the component is loading or not
  - prop_name (character; optional): holds which property is loading
  - component_name (character; optional): holds the name of the component that is loading. Object that holds the loading state object coming from dash-renderer}

\item{maxCameraOrbit}{Character. Maximum camera orbit bounds}

\item{maxFieldOfView}{Character. Maximum camera field of view}

\item{minCameraOrbit}{Character. Minimum camera orbit bounds}

\item{minFieldOfView}{Character. Minimum camera field of view}

\item{poster}{Character. Poster image URL}

\item{shadowIntensity}{Numeric | character. }

\item{src}{Character. Model source URL (.glb or .gltf)}

\item{style}{Named list. CSS Style object}

\item{toneMapping}{A value equal to: 'neutral', 'aces', 'agx', 'reinhard', 'cineon', 'linear', 'none'. }

\item{touchAction}{A value equal to: 'pan-y', 'pan-x', 'none'. Touch action behavior}

\item{variantName}{Character. }
}

\value{named list of JSON elements corresponding to React.js properties and their values}

