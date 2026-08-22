import logging
import re
from pathlib import Path
from typing import List, Optional

import dash
import dash_mantine_components as dmc
import frontmatter
from dash import html
from dash_improve_my_llms import register_page_metadata
from markdown2dash import Admonition, BlockExec, Divider, Image, create_parser
from pydantic import BaseModel

from lib.ad_client import inject_ad_into_aside
from lib.constants import OG_IMAGE_URL, PAGE_TITLE_PREFIX, NAME_CONTENT_MAP
from lib import page_tiers
from lib.directives.headings import patch_renderer
from lib.directives.kwargs import Kwargs
from lib.directives.llms_copy import LlmsCopy
from lib.directives.source import SC
from lib.directives.toc import TOC

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

directory = "docs"

# read all markdown files
files = Path(directory).glob("**/*.md")


class Meta(BaseModel):
    name: str
    description: str
    endpoint: str
    package: str = "dash_pydantic_form"
    category: Optional[str] = None
    icon: Optional[str] = None
    # Who may read this page: public | auth | admin | hidden. Absent means
    # public — see lib/page_tiers.py for the tier model and why the default
    # is open. Enforced only when access control is wired in run.py.
    tier: Optional[str] = None


_SOURCE_DIRECTIVE = re.compile(r'^\.\. source::(.+?)$', re.MULTILINE)
_LANG_MAP = {
    'py': 'python', 'pyi': 'python',
    'js': 'javascript', 'jsx': 'jsx',
    'ts': 'typescript', 'tsx': 'tsx',
    'css': 'css', 'scss': 'scss', 'sass': 'sass', 'less': 'less',
    'html': 'html', 'htm': 'html', 'xml': 'xml',
    'json': 'json',
    'yaml': 'yaml', 'yml': 'yaml',
    'md': 'markdown', 'rst': 'rst', 'txt': 'text',
    'sh': 'bash', 'bash': 'bash',
    'sql': 'sql', 'r': 'r',
    'toml': 'toml', 'ini': 'ini', 'conf': 'conf',
}


def _expand_source_directives(markdown_content: str) -> str:
    """Inline `.. source::path` directives with the referenced file content.

    This produces the prose that dash-improve-my-llms 2.0 will serve at
    `/<page>/llms.txt`. Replacing the directive with the real file content
    is what makes the LLM output self-contained for the "paste into a chat
    window" audience.
    """
    def replace(match: re.Match) -> str:
        file_path = match.group(1).strip()
        try:
            full = Path(file_path)
            content = full.read_text()
            ext = full.suffix.lstrip('.').lower()
            lang = _LANG_MAP.get(ext, ext or 'text')
            tail = '' if content.endswith('\n') else '\n'
            return f'\n```{lang}\n# File: {file_path}\n\n{content}{tail}```\n'
        except FileNotFoundError:
            return f'\n<!-- Error: File not found: {file_path} -->\n'
        except Exception as exc:
            return f'\n<!-- Error reading {file_path}: {exc} -->\n'

    return _SOURCE_DIRECTIVE.sub(replace, markdown_content)


def _build_llms_doc(name: str, description: str, expanded_markdown: str, path: str) -> str:
    """Wrap the expanded markdown with the heading/description preamble that
    /llms.txt readers expect."""
    parts: List[str] = [f"# {name}\n"]
    if description:
        parts.append(f"> {description}\n")
    parts.append("---\n")
    parts.append(expanded_markdown.rstrip() + "\n")
    parts.append("\n---\n")
    parts.append(f"*Source: {path}*\n")
    return "\n".join(parts)


# Headings containing inline code/emphasis crash markdown2dash's renderer and,
# when they don't, get an id their own TOC anchor doesn't match. Must run
# before create_parser() instantiates the renderer. See lib/directives/headings.
patch_renderer()

directives = [Admonition(), BlockExec(), Divider(), Image(), Kwargs(), LlmsCopy(), SC(), TOC()]
parse = create_parser(directives)

for file in files:
    logger.info("Loading %s..", file)
    metadata, content = frontmatter.parse(file.read_text())
    metadata = Meta(**metadata)

    # Store raw markdown content in NAME_CONTENT_MAP for the LLM copy button.
    NAME_CONTENT_MAP[metadata.name] = content

    layout = parse(content)

    # add heading and description to the layout
    section = [
        dmc.Title(metadata.name, order=2, className="m2d-heading"),
        dmc.Text(metadata.description, className="m2d-paragraph"),
    ]
    layout = section + layout

    # 2plot.dev ad network: append the ad slot below the TOC links inside
    # the page's aside (pages without `.. toc::` simply get no ad).
    inject_ad_into_aside(layout, metadata.endpoint)

    # Wrap the whole page in ONE container with a page-unique id. dash-renderer
    # keys React children by component id, and markdown2dash gives every heading
    # an id derived from its text ("usage", "introduction", ...) so TOC anchors
    # work. Those ids repeat within and across pages, so when fast navigation
    # swaps _pages_content.children between two flat layout lists, React
    # reconciles by colliding keys and splices stale headings from the previous
    # page into the new one (TOC-only ghost page until you scroll). A single
    # keyed wrapper per page makes every swap old-node -> new-node: atomic
    # unmount/mount, no cross-page key matching. Do not flatten this back into
    # a list.
    layout = html.Div(
        layout, id="m2d-page" + metadata.endpoint.replace("/", "-")
    )

    # register with dash
    dash.register_page(
        metadata.name,
        metadata.endpoint,
        name=metadata.name,
        title=PAGE_TITLE_PREFIX + metadata.name,
        description=metadata.description,
        layout=layout,
        category=metadata.category,
        icon=metadata.icon,
        # Without this Dash infers an image from assets/ and finds `logo.svg` —
        # an SVG, which every social scraper rejects — then emits it ALONGSIDE
        # the og:image in templates/index.html. See lib.constants.OG_IMAGE_URL.
        image_url=OG_IMAGE_URL,
    )

    # Feed the expanded markdown into dash-improve-my-llms so /<page>/llms.txt
    # serves the directive-expanded prose. This replaces the custom Flask
    # route that used to live in run.py and works across all three backends.
    # Record the declared tier before the prose is registered, so a gate can
    # never be applied later than the content it is meant to gate.
    page_tiers.register(metadata.endpoint, metadata.tier)

    expanded = _expand_source_directives(content)
    register_page_metadata(
        path=metadata.endpoint,
        name=metadata.name,
        description=metadata.description,
        llms_doc=_build_llms_doc(metadata.name, metadata.description, expanded, metadata.endpoint),
    )
