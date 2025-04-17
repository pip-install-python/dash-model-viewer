import dash
from dash import html
from dash.dependencies import Input, Output
from dash_model_viewer import DashModelViewer

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("Augmented Reality with Model Viewer"),
    DashModelViewer(
        id="3d-model",
        src="https://modelviewer.dev/shared-assets/models/Astronaut.glb",
        alt="A 3D model of an astronaut",
        cameraControls=True,
        touchAction="pan-y",
        ar=True,
        poster="https://modelviewer.dev/shared-assets/models/Astronaut.webp",
        hotspots=[
            {"position": "0 1.5 0.5", "normal": "0 0 1", "orbit": "45deg 60deg 2m", "target": "0 1 0", "text": "Helmet"},
            {"position": "0.25 0.75 0.75", "normal": "1 0 0", "orbit": "-30deg 75deg 1.5m", "target": "0.25 0.75 0", "text": "Arm"}
        ],
        style={"height": "1000px", "width": "100%"},
        arButtonText="View in AR"
    ),
    html.Div([
        html.Button('Astronaut', id='astronaut-button', n_clicks=0),
        html.Button('Flight Helmet', id='helmet-button', n_clicks=0),
    ], style={'marginTop': '20px'})
])

@app.callback(
    Output('3d-model', 'src'),
    [Input('astronaut-button', 'n_clicks'),
     Input('helmet-button', 'n_clicks')]
)
def update_model(astronaut_clicks, helmet_clicks):
    ctx = dash.callback_context
    if not ctx.triggered:
        return "https://modelviewer.dev/shared-assets/models/Astronaut.glb"
    else:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if button_id == 'astronaut-button':
            return "https://modelviewer.dev/shared-assets/models/Astronaut.glb"
        elif button_id == 'helmet-button':
            return "https://modelviewer.dev/shared-assets/models/DamagedHelmet.glb"

if __name__ == '__main__':
    app.run(debug=True, port=5431)