from pathlib import Path

import dash_mantine_components as dmc
import frontmatter
from dash import register_page
from markdown2dash import Admonition, Divider, Image, create_parser

import dash_model_viewer as dmv
from lib.constants import OG_IMAGE_URL, PAGE_TITLE_PREFIX, SITE_DESCRIPTION
from lib.demo_models import ASTRONAUT
from lib.directives.headings import patch_renderer
from lib.versions import substitute_versions

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

# Same {{VERSION:<distribution>}} substitution pages/markdown.py applies to the
# docs. The home page is the most-read surface in the network (it IS /llms.txt),
# so any version number on it must come from the installed distribution rather
# than from prose — the fleet shipped "Powered by 2.3.4" for months while a
# newer package was actually serving the site.
content = substitute_versions(content, source=str(md_file))

# Module-level LLMS_DOC — dash-improve-my-llms picks this up automatically and
# serves it as the opening prose of /llms.txt. No layout walking, no extraction.
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
    # markdown2dash, not dcc.Markdown (the fleet's no-`dcc` rule, sync item
    # 16): the same renderer the docs pages use, so home and docs share one
    # typography and one set of DMC components. patch_renderer() also adds the
    # inline-image renderer markdown2dash lacks.
    #
    # SPLATTED, not nested. `create_parser(...)(content)` returns a LIST, and
    # the template assigns that list AS `children`. This page prepends a hero,
    # so the obvious `children=[hero, parsed]` puts a list INSIDE the children
    # list — and Dash's renderer does not descend into a nested list: every
    # component in it reaches React as a raw `{props, type, namespace}` object
    # and React refuses it (Minified error #31), blanking the whole page while
    # the header and footer render normally. Measured on the wire at 576880d:
    # /_dash-update-component returned `children: [Paper, ARRAY len 32]`, the
    # only nested array on any page of this site, and the console carried 20
    # copies of #31. Docs pages never hit it because pages/markdown.py assigns
    # the parsed list directly.
    children=[
        dmc.Paper(hero, withBorder=True, radius="md", p=0, mb="xl",
                  style={"overflow": "hidden"}),
        *(patch_renderer(), create_parser([Admonition(), Divider(), Image()])(content))[1],
    ],
)
