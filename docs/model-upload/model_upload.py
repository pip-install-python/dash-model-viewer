import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html, no_update

import dash_model_viewer as dmv
from lib import demo_models, glb, uploads

VIEWER_ATTRS = {
    "environment-image": "neutral",
    "exposure": "1.05",
    "shadow-softness": "0.7",
    # Bare boolean attributes are passed as the empty string — `auto-rotate`
    # has no named prop, and the shim writes presence rather than a value.
    "auto-rotate": "",
    "auto-rotate-delay": "1200",
}

#: Rows are (label, key, formatter). Declared once so the table and its test
#: read the same list — a stats panel that drifts from what it measures is
#: worse than no stats panel.
ROWS = [
    ("Format", "version", lambda v: f"glTF {v}"),
    ("Written by", "generator", str),
    ("Nodes", "nodes", "{:,}".format),
    ("Meshes", "meshes", "{:,}".format),
    ("Triangles", "triangles", "{:,}".format),
    ("Materials", "materials", "{:,}".format),
    ("Textures", "textures", "{:,}".format),
    ("Animations", "animations", "{:,}".format),
    ("Size", "bytes", lambda v: f"{v / 1048576:.2f} MB"),
]


def _table(summary):
    body = [
        dmc.TableTr([dmc.TableTd(label), dmc.TableTd(fmt(summary[key]))])
        for label, key, fmt in ROWS
    ]
    extras = []
    if summary["animation_names"]:
        named = ", ".join(n for n in summary["animation_names"] if n) or "unnamed"
        extras.append(dmc.TableTr([dmc.TableTd("Clips"), dmc.TableTd(named)]))
    if summary["extensions"]:
        extras.append(dmc.TableTr([
            dmc.TableTd("Extensions"),
            dmc.TableTd(", ".join(summary["extensions"])),
        ]))
    return dmc.Table(
        striped=True, withTableBorder=True, verticalSpacing="4px",
        children=[dmc.TableTbody(body + extras)],
    )


component = html.Div(
    [
        dcc.Store(id="mu-summary"),
        dmc.Group(
            [
                dcc.Upload(
                    id="mu-upload",
                    accept=".glb,model/gltf-binary",
                    multiple=False,
                    children=dmc.Button("Choose a .glb file"),
                ),
                dmc.Text(id="mu-status", size="sm", c="dimmed"),
            ],
            mb="xs",
            align="center",
        ),
        dmc.Grid(
            gutter="md",
            children=[
                dmc.GridCol(
                    dmv.ModelViewer(
                        id="mu-viewer",
                        src=demo_models.ASTRONAUT,
                        alt="An uploaded glTF binary model",
                        camera_controls=True,
                        shadow_intensity=1,
                        attributes=VIEWER_ATTRS,
                        style={"width": "100%", "height": "460px"},
                    ),
                    span={"base": 12, "md": 7},
                ),
                dmc.GridCol(
                    html.Div(id="mu-facts"),
                    span={"base": 12, "md": 5},
                ),
            ],
        ),
    ]
)


@callback(
    Output("mu-viewer", "src"),
    Output("mu-viewer", "alt"),
    Output("mu-status", "children"),
    Output("mu-facts", "children"),
    Output("mu-summary", "data"),
    Input("mu-upload", "contents"),
    State("mu-upload", "filename"),
    prevent_initial_call=True,
)
def show_model(contents, filename):
    """Validate the upload, describe it, and hand it to the viewer.

    THE FILE IS IDENTIFIED BY ITS CONTENT, not by the media type the browser
    guessed: a `.glb` is recognised by its magic number and version field, so a
    renamed ZIP is refused with a sentence rather than reaching the viewer and
    silently failing to draw. The rules live in `lib/uploads.py` beside the
    image ones, so the two cannot drift into different caps.

    Nothing is written to disk. The bytes are validated, measured, and handed
    straight back as the `data:` URL the viewer reads.
    """
    raw, message = uploads.decode_model(contents, filename)
    if raw is None:
        return no_update, no_update, message, no_update, no_update

    try:
        summary = glb.summarize(raw)
    except (ValueError, KeyError, IndexError):
        return (no_update, no_update,
                f"{filename or 'that file'} is a glTF container this page "
                f"cannot read — its JSON chunk is malformed.",
                no_update, no_update)

    name = filename or "the uploaded model"
    return (
        contents,
        f"{name}, an uploaded glTF binary model",
        f"{name} — {message}",
        _table(summary),
        summary,
    )
