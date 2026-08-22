import json

from dash import ALL, Input, Output, State, callback, ctx, html, no_update
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib import sculptor

IDEAS = [
    "a brutalist lighthouse at dusk, weathered concrete and one warm light",
    "a desert observatory, sandstone and brass, dish pointed at the sky",
    "a bonsai on a stone plinth, copper pot, moss",
    "a cathedral of stacked glass cubes lit from inside",
]

# A neutral studio environment plus a real shadow — generated art looks flat
# and grey without image-based lighting, which reads as "broken" rather than
# "dark". This is the one place the demo needs opinionated defaults.
VIEWER_ATTRS = {
    "environment-image": "neutral",
    "exposure": "1.1",
    "shadow-softness": "0.7",
}

component = html.Div(
    [
        dmc.Group(
            [
                dmc.TextInput(
                    id="g3-prompt",
                    placeholder="Describe a sculpture…",
                    value=IDEAS[0],
                    style={"flex": 1},
                ),
                dmc.Button("Sculpt", id="g3-go", variant="filled"),
            ],
            mb="xs",
            align="flex-end",
        ),
        dmc.Group(
            [
                dmc.Badge(idea.split(",")[0], id={"type": "g3-idea", "i": i},
                          variant="light", style={"cursor": "pointer"})
                for i, idea in enumerate(IDEAS)
            ],
            gap="xs",
            mb="sm",
        ),
        # The sculpt call takes several seconds. Without a visible busy state
        # the page looks broken — you click, nothing moves, and there is no way
        # to tell a slow call from a dead one. The overlay sits over the viewer
        # rather than replacing it, so the previous sculpture stays on screen
        # while the next one is composed.
        dmc.Box(
            pos="relative",
            children=[
                dmc.LoadingOverlay(
                    id="g3-busy",
                    visible=False,
                    zIndex=10,
                    overlayProps={"radius": "md", "blur": 2},
                    loaderProps={"type": "bars", "color": "indigo"},
                ),
                dmv.ModelViewer(
                    id="g3-viewer",
                    # Placeholder until the first sculpt: one primitive built by
                    # the same writer, so the page is never an empty box.
                    src=sculptor.to_data_url(
                        sculptor.build(
                            {
                                "parts": [
                                    {"shape": "torus", "name": "seed",
                                     "size": {"x": 1.2, "y": 0.1, "z": 0.24},
                                     "position": {"x": 0, "y": 0.6, "z": 0},
                                     "rotation": {"x": 90, "y": 0, "z": 0},
                                     "color": "#4C6EF5", "metallic": 0.9,
                                     "roughness": 0.25, "emissive_strength": 0.0},
                                ]
                            }
                        )[0]
                    ),
                    alt="A generated 3D sculpture",
                    camera_controls=True,
                    shadow_intensity=1,
                    interpolation_decay=90,
                    attributes=VIEWER_ATTRS,
                    style={"width": "100%", "height": "440px"},
                ),
            ],
        ),
        dmc.Text(
            # Measured, not guessed: a sculpt runs ~35s (effort="medium", and the
        # composition reasoning is the slow part). An estimate that is too
        # low is worse than none — the user concludes it has hung.
        "Composing — this takes about 30 to 45 seconds.",
            id="g3-working", size="sm", c="dimmed", mt="xs", display="none",
        ),
        dmc.Alert(id="g3-status", mt="sm", color="indigo", hide=True),
        dmc.Spoiler(
            id="g3-spoiler",
            showLabel="Show the parts list",
            hideLabel="Hide",
            maxHeight=0,
            children=dmc.Code(id="g3-json", block=True),
            mt="xs",
        ),
    ]
)


@callback(
    Output("g3-prompt", "value"),
    Input({"type": "g3-idea", "i": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def use_idea(clicks):
    if not any(clicks or []):
        return no_update
    return IDEAS[ctx.triggered_id["i"]]


@callback(
    Output("g3-viewer", "src"),
    Output("g3-viewer", "alt"),
    Output("g3-status", "children"),
    Output("g3-status", "color"),
    Output("g3-status", "hide"),
    Output("g3-json", "children"),
    Input("g3-go", "n_clicks"),
    State("g3-prompt", "value"),
    # Dash sets each of these to the middle value while the callback runs and
    # the last value when it finishes. None of them collide with an Output the
    # callback itself returns — that would race.
    running=[
        (Output("g3-busy", "visible"), True, False),
        (Output("g3-go", "loading"), True, False),
        (Output("g3-prompt", "disabled"), True, False),
        (Output("g3-working", "display"), "block", "none"),
    ],
    prevent_initial_call=True,
)
def sculpt(_, prompt):
    result = sculptor.sculpt(prompt)

    if not result.ok:
        return no_update, no_update, result.reason, "yellow", False, no_update

    manifest = result.manifest
    note = f"{manifest.get('name', 'Untitled')} — {manifest.get('notes', '')}"
    if result.notes:
        note += "  ·  " + "; ".join(result.notes)
    note += f"  ·  {result.part_count} parts, {len(result.glb) / 1024:.0f} KB"

    return (
        result.data_url,
        f"A generated 3D sculpture: {manifest.get('name', prompt)}",
        note,
        "indigo",
        False,
        json.dumps(manifest, indent=2),
    )
