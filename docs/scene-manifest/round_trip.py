import pathlib

from dash import Input, Output, State, callback, dcc, html, no_update
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib import manifest

SAMPLES = pathlib.Path(__file__).parent / "samples"

#: The three valid samples, plus the refusal fixture kept deliberately apart.
#: All four are committed JSON — nothing on this page calls a model, which is
#: the point: the round trip works on a host with no API key.
SAMPLE_FILES = {
    "Lighthouse (2 parts)": "lighthouse.json",
    "Colonnade (28 parts — the limit)": "colonnade.json",
    "Brazier (emissive)": "brazier.json",
    "Cart (v2 — a wheel placed four times)": "cart.json",
    "Cart, written flat (v1 — the same sculpture)": "cart-flat.json",
}
FIXTURE = "INVALID-fixture.json"


def _read(name):
    return (SAMPLES / name).read_text(encoding="utf-8")


_FIRST = _read("lighthouse.json")
_INITIAL_GLB, _, _ = manifest.render(manifest.loads(_FIRST))

component = html.Div(
    [
        dcc.Download(id="sm-download-json"),
        dcc.Download(id="sm-download-glb"),
        dmc.Grid(
            gutter="md",
            children=[
                dmc.GridCol(
                    dmc.Stack(
                        gap="xs",
                        children=[
                            dmc.Select(
                                id="sm-sample",
                                label="Load a sample",
                                data=list(SAMPLE_FILES),
                                value=next(iter(SAMPLE_FILES)),
                                allowDeselect=False,
                            ),
                            dmc.Textarea(
                                id="sm-text",
                                label="Manifest",
                                value=_FIRST,
                                autosize=False,
                                minRows=14,
                                styles={"input": {"fontFamily": "monospace",
                                                  "fontSize": "11px"}},
                            ),
                            dmc.Group(
                                [
                                    dmc.Button("Render", id="sm-render"),
                                    dmc.Button("Export JSON", id="sm-export",
                                               variant="light"),
                                    dmc.Button("Download .glb", id="sm-glb",
                                               variant="light"),
                                    dmc.Button("Load the invalid fixture",
                                               id="sm-break", variant="subtle",
                                               color="orange"),
                                ],
                                gap="xs",
                            ),
                        ],
                    ),
                    span={"base": 12, "md": 6},
                ),
                dmc.GridCol(
                    [
                        dmv.ModelViewer(
                            id="sm-viewer",
                            src=manifest.sculptor.to_data_url(_INITIAL_GLB),
                            alt="A sculpture rendered from a committed scene manifest",
                            camera_controls=True,
                            shadow_intensity=1,
                            attributes={"environment-image": "neutral",
                                        "shadow-softness": "0.6"},
                            style={"width": "100%", "height": "420px"},
                        ),
                        dmc.Alert(id="sm-status", mt="xs", color="indigo",
                                  children="Rendered from the committed sample. "
                                           "No model was called."),
                    ],
                    span={"base": 12, "md": 6},
                ),
            ],
        ),
    ]
)


@callback(
    Output("sm-text", "value"),
    Input("sm-sample", "value"),
    Input("sm-break", "n_clicks"),
    prevent_initial_call=True,
)
def load_file(label, _break_clicks):
    from dash import ctx

    if ctx.triggered_id == "sm-break":
        return _read(FIXTURE)
    return _read(SAMPLE_FILES[label])


@callback(
    Output("sm-viewer", "src"),
    Output("sm-viewer", "alt"),
    Output("sm-status", "children"),
    Output("sm-status", "color"),
    Input("sm-render", "n_clicks"),
    State("sm-text", "value"),
    prevent_initial_call=True,
)
def render(_clicks, text):
    """Import, validate, render. Nothing is stored.

    The refusal message is the importer's own — it names the field and its path
    — rather than a sentence written for the page. That is why the invalid
    fixture is a committed file: a typed-out error message could say anything.
    """
    try:
        parsed = manifest.loads(text or "")
        data, notes, used = manifest.render(parsed)
    except manifest.ManifestError as exc:
        return no_update, no_update, f"Refused — {exc}", "yellow"

    name = parsed.get("name", "untitled")
    detail = f"{used} parts, {len(data) / 1024:.0f} KB"
    if notes:
        detail += "  ·  " + "; ".join(notes)
    return (
        manifest.sculptor.to_data_url(data),
        f"A sculpture rendered from a scene manifest: {name}",
        f"Rendered {name} — {detail}. No model was called.",
        "indigo",
    )


@callback(
    Output("sm-download-json", "data"),
    Input("sm-export", "n_clicks"),
    State("sm-text", "value"),
    prevent_initial_call=True,
)
def export_json(_clicks, text):
    """Export the NORMALISED manifest — byte-stable, so two exports of the same
    scene are identical and a diff shows only what you changed.

    The bytes are already in hand; there is no server-side path and nothing is
    written to disk.
    """
    try:
        parsed = manifest.loads(text or "")
    except manifest.ManifestError:
        return no_update
    return {
        "content": manifest.dumps(parsed),
        "filename": manifest.filename(parsed, "json"),
    }


@callback(
    Output("sm-download-glb", "data"),
    Input("sm-glb", "n_clicks"),
    State("sm-text", "value"),
    prevent_initial_call=True,
)
def download_glb(_clicks, text):
    """Hand over the rendered bytes.

    Built in memory and written straight into the response buffer: there is no
    server-side path, no store, no temp file and nothing to clean up. That is
    the same reasoning that keeps the viewer's own `src` a `data:` URL.
    """
    try:
        parsed = manifest.loads(text or "")
        data, _notes, _used = manifest.render(parsed)
    except manifest.ManifestError:
        return no_update
    return dcc.send_bytes(data, manifest.filename(parsed, "glb"))
