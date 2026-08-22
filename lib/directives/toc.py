import dash_mantine_components as dmc
from dash import html
from dash.development.base_component import Component

from markdown2dash import TableOfContents

from lib.directives.headings import slugify


class TOC(TableOfContents):
    def hook(self, md, state):
        """Build the entries, then re-slug them the way headings are slugged.

        markdown2dash slugs the *raw* markdown of each heading, so
        ``## The `peers` tier`` yields the anchor ``#the-`peers`-tier`` while
        the rendered ``dmc.Title`` carries a different id — the link lands
        nowhere and does it silently. `slugify` is the same function
        lib/directives/headings.py gives the renderer, so the two agree.

        The link label keeps its markdown markers stripped too; a sidebar
        entry reading "The `peers` tier" with literal backticks is noise.
        """
        super().hook(md, state)

        for token in state.tokens:
            if token["type"] != "block_toc":
                continue
            attrs = token.get("attrs", {})
            attrs["table_of_contents"] = [
                (level, _label(text), slugify(text))
                for level, text, _ in attrs.get("table_of_contents", [])
            ]

    def render(self, renderer, title: str, content: str, **options) -> Component:
        table_of_contents = options.pop("table_of_contents")
        paddings = {3: 0, 4: 20, 5: 40}
        links = [
            html.A(
                dmc.Text(text, c="dimmed", size="sm", variant="text"),
                href="#" + hid,
                style={
                    "textTransform": "capitalize",
                    "textDecoration": "none",
                    "paddingLeft": paddings[level],
                    "width": "fit-content",
                },
            )
            for level, text, hid in table_of_contents
            if level >= 3
        ]

        heading = dmc.Text(title, mb=10, fw=500) if links else None

        content = dmc.Stack([
            heading, *links, dmc.Space(h=20)
        ], gap=6, px=25)
        return dmc.AppShellAside(
            children=dmc.ScrollArea(content, type="never"), withBorder=False
        )


def _label(text: str) -> str:
    """The heading, minus inline markdown markers, for display in the aside."""
    from lib.directives.headings import _INLINE_MARKERS, _MD_LINK

    return _INLINE_MARKERS.sub("", _MD_LINK.sub(r"\1", text)).strip()
