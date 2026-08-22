import importlib
import inspect
from markdown2dash.src.directives.kwargs import Kwargs as KwargsBase


def convert_docstring_to_dict(docstring):
    """Convert numpy style parameter docstring to a list of dicts with keys name, type, description"""

    lines: list[str] = docstring.split("----------\n")[-1].split("\n")

    params = []
    new_param = None
    for line in lines:
        if not line.startswith("    "):
            if new_param is not None:
                params.append(new_param)
            name, type = line.split(": ", 1)
            new_param = {"name": name, "type": type, "description": ""}
        else:
            new_param["description"] += " " + line.strip()
    params.append(new_param)

    return params


class Kwargs(KwargsBase):

    def hook(self, md, state):
        sections = []

        for tok in state.tokens:
            if tok["type"] == self.block_name:
                sections.append(tok)

        for section in sections:
            attrs = section["attrs"]

            # Parse the component specification (e.g., "dmc.Button" or "html.Div")
            component_spec = attrs["title"]

            # Common package name mappings
            package_map = {
                "dmc": "dash_mantine_components",
                "html": "dash.html",
                "dcc": "dash.dcc",
                "dash": "dash"
            }

            # Try to parse package.Component format
            if "." in component_spec:
                package_abbr, component_name = component_spec.rsplit(".", 1)
                package = package_map.get(package_abbr, package_abbr)
            else:
                # If no package specified, use default or library attribute
                package = attrs.pop("library", "dash_mantine_components")
                component_name = component_spec

            try:
                imported = importlib.import_module(package)
                component = getattr(imported, component_name)
                docstring = inspect.getdoc(component)

                if docstring and "----------" in docstring:
                    # numpy-style (dash-mantine-components hand-written docs)
                    docstring = docstring.split("----------\n")[-1]
                    attrs["kwargs"] = convert_docstring_to_dict(docstring)
                elif docstring and "Keyword arguments:" in docstring:
                    # dash-generate-components style — every component a
                    # library satellite documents. The base markdown2dash
                    # Kwargs ships a parser for exactly this format; this
                    # numpy override used to SHADOW it, so dash-built
                    # components rendered silently EMPTY props tables
                    # (found on muicharts' /api; pannellum's /api likely
                    # affected too). Fall back to the base parser.
                    from markdown2dash.src.utils import (
                        convert_docstring_to_dict as dash_convert,
                    )

                    attrs["kwargs"] = dash_convert(
                        docstring.split("Keyword arguments:")[-1]
                    )
                else:
                    attrs["kwargs"] = []
            except Exception:
                # Import failed or the component has no usable docstring;
                # a props table is a nice-to-have, not worth failing a page for.
                attrs["kwargs"] = []
