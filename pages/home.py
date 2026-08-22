from pathlib import Path

import dash_mantine_components as dmc
import frontmatter
from dash import dcc, register_page

import dash_model_viewer as dmv
from lib.constants import OG_IMAGE_URL, PAGE_TITLE_PREFIX, SITE_DESCRIPTION
from lib.demo_models import ASTRONAUT

register_page(
    __name__,
    "/",
    title=PAGE_TITLE_PREFIX + "Home",
    # Dash emits `description`, `og:description` and `twitter:description` for
    # every page from this argument, and emits them EMPTY when it is missing —
    # which is what the home page, the most-linked page on the site, was doing.
    description=SITE_DESCRIPTION,
    # The most-shared page on the site. See lib.constants.OG_IMAGE_URL for why
    # this is explicit rather than inferred from assets/.
    image_url=OG_IMAGE_URL,
)

# read the home page markdown
md_file = Path("pages") / "home.md"

post = frontmatter.loads(md_file.read_text())
metadata, content = post.metadata, post.content

# Module-level LLMS_DOC — dash-improve-my-llms 2.0 picks this up automatically
# and serves it verbatim at /llms.txt. No layout walking, no extraction.
LLMS_DOC = content

# The hero is the product. A documentation site for a 3D component whose front
# page is a screenshot has already lost the argument, so the first thing on the
# page is a real, draggable viewer — which doubles as the smoke test: if this
# renders, the hook, the vendored bundle and the shim all work.
hero = dmv.ModelViewer(
    id="home-viewer",
    src=ASTRONAUT,
    alt="A 3D model of an astronaut in a white spacesuit — drag to orbit",
    camera_orbit="15deg 78deg 4m",
    camera_target="0m 1m 0m",
    interpolation_decay=120,
    shadow_intensity=1,
    style={
        "width": "100%",
        "height": "clamp(320px, 45vh, 520px)",
        "borderRadius": "var(--mantine-radius-md)",
    },
)

layout = dmc.Container(
    # Page-unique id: keeps React's keyed reconciliation of page swaps atomic
    # (see the wrapper comment in pages/markdown.py).
    id="m2d-page-home",
    size="lg",
    py="xl",
    children=[
        dmc.Paper(hero, withBorder=True, radius="md", p=0, mb="xl",
                  style={"overflow": "hidden"}),
        dcc.Markdown(
            content,
            style={
                "maxWidth": "none",  # Allow Container to control width
            },
        ),
    ],
)
