from dash import Input, Output, clientside_callback, callback, dcc, html
import dash_mantine_components as dmc

import dash_model_viewer as dmv
from lib import uploads
from lib.demo_models import ASTRONAUT

#: 4 MiB of decoded image. A base-colour texture larger than this is a slow
#: upload for a demo and, past roughly 4096x4096, more detail than the GPU will
#: show on a 420px viewer anyway. Stated here, stated on the page, and pinned
#: by tests/test_texture_upload.py — a cap that is documented and not enforced
#: is the shape of defect this package spent 1.0.0 removing.
MAX_TEXTURE_BYTES = 4 * 1024 * 1024

#: Raster formats `model-viewer`'s `createTexture` accepts and a browser will
#: decode without a plugin. SVG is deliberately absent: it is a scriptable
#: document, not an image, and this one is handed straight to the DOM.
ACCEPTED_TYPES = uploads.IMAGE_TYPES


def validate_texture(contents, filename=None):
    """Check a ``dcc.Upload`` value. Returns ``(data_url_or_None, message)``.

    The rules themselves live in ``lib/uploads.py``, shared with
    /sculpt-from-image: two pages taking an image from a visitor need the same
    answers about type, size and what happens to the bytes, and two copies of
    those answers is two places for them to drift.

    Pure, so it can be tested without a browser or a running app. The bytes are
    decoded only to MEASURE them — nothing here writes to disk, and the file
    never leaves the request that carried it.
    """
    raw, _media_type, message = uploads.decode_image(
        contents, filename, max_bytes=MAX_TEXTURE_BYTES, accepted=ACCEPTED_TYPES
    )
    if raw is None:
        return None, message
    return contents, f"{message} — applied below."


component = html.Div(
    [
        dcc.Store(id="tx-store"),
        dmc.Group(
            [
                dcc.Upload(
                    id="tx-upload",
                    accept="image/png,image/jpeg",
                    multiple=False,
                    children=dmc.Button("Upload a texture (PNG or JPEG)"),
                ),
                dmc.Text(id="tx-status", size="sm", c="dimmed"),
            ],
            mb="sm",
        ),
        dmv.ModelViewer(
            id="tx-viewer",
            src=ASTRONAUT,
            alt="An astronaut whose base-colour texture is replaced by an uploaded image",
            camera_controls=True,
            shadow_intensity=1,
            style={"width": "100%", "height": "420px"},
        ),
        dmc.Text(id="tx-applied", size="sm", c="dimmed", mt="xs"),
    ]
)


@callback(
    Output("tx-store", "data"),
    Output("tx-status", "children"),
    Input("tx-upload", "contents"),
    Input("tx-upload", "filename"),
    prevent_initial_call=True,
)
def accept_upload(contents, filename):
    return validate_texture(contents, filename)


# Swapping a material's texture is an imperative call on the element — there is
# no prop for it, and 1.0.0 deliberately ships no imperative surface. So this
# is one of the few places the escape hatch is a clientside callback rather
# than `attributes` / `mv_*`.
#
# It reports back how many materials it touched, because the failure that
# matters is silent: a material with no base-colour texture slot has nothing
# to swap, and the upload would otherwise appear to do nothing at all.
clientside_callback(
    """
    async function (dataUrl) {
        if (!dataUrl) { return window.dash_clientside.no_update; }
        const viewer = document.getElementById('tx-viewer');
        if (!viewer || !viewer.model) {
            return 'The model is still loading — try again in a moment.';
        }
        try {
            const texture = await viewer.createTexture(dataUrl);
            const materials = viewer.model.materials || [];
            let applied = 0;
            materials.forEach(function (material) {
                const slot = material.pbrMetallicRoughness.baseColorTexture;
                if (slot) { slot.setTexture(texture); applied += 1; }
            });
            if (!applied) {
                return 'This model has no base-colour texture slot to replace.';
            }
            return 'Applied to ' + applied + ' of ' + materials.length + ' materials.';
        } catch (err) {
            console.error('texture upload failed', err);
            return 'The browser could not decode that image.';
        }
    }
    """,
    Output("tx-applied", "children"),
    Input("tx-store", "data"),
    prevent_initial_call=True,
)
