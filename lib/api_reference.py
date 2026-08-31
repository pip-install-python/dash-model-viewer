"""Component prop tables from an installed Dash component package (1.6.38).

Three sources, in order (1.6.41 — leaflet's and modelviewer's findings):

1. ``metadata.json`` next to the package's ``__init__`` — react-docgen
   output: one entry per component source file with ``displayName`` and
   ``props`` → ``{type, required, description, defaultValue}``. On a
   pip-installed package it is there; in a component REPO it can be a
   27 MB gitignored build artifact excluded from the wheel (leaflet), so
   /api passes locally and is EMPTY on the host.
2. ``api_metadata.json`` next to the package — the committed extract
   ``scripts/build_api_metadata.py`` writes in this module's output shape
   (~1% of the size), stamped ``generated`` for the sitemap lastmod.
3. The component classes' docstrings — Dash's generated classes list
   every prop under ``Keyword arguments:`` as ``- name (type; optional):
   description``; hook-based packages ship no metadata at all
   (modelviewer) and this is what remains.

(The drop named ``_prop_names``; Dash 4 no longer sets it on generated
classes — the docstring and metadata.json are what exist.)

THIS FORK'S SOURCE 3 IS WIDER THAN THE TEMPLATE'S. `dash_model_viewer` is
hook-based since 1.0.0: no generator, no build, and deliberately no
``metadata.json`` (``tests/test_no_regeneration.py`` fails if one reappears;
``.claude/ARCHITECTURE.md`` is why). Its components are hand-authored classes
whose docstrings carry the same ``Keyword arguments:`` list a generated class
carries — but INDENTED, with the description on the following line, which the
template's one-line regex never matches (measured: zero props). So source 3
here reads the docstring for descriptions AND the ``__init__`` signature for
type, default and required. Same four columns, from the sources this package
actually has. Recorded as DIVERGENCES §12.
"""
from __future__ import annotations

import importlib
import inspect
import json
import re
import typing
from pathlib import Path

SLIM_METADATA = "api_metadata.json"
_SKIP_PROPS = ("setProps", "loading_state")


def _type_name(t) -> str:
    if not isinstance(t, dict):
        return str(t or "")
    name = t.get("name") or ""
    if name == "enum" and isinstance(t.get("value"), list):
        vals = [str(v.get("value", v)) for v in t["value"]]
        return "one of " + ", ".join(vals[:8]) + (" …" if len(vals) > 8 else "")
    if name == "union" and isinstance(t.get("value"), list):
        return " | ".join(_type_name(v) for v in t["value"])
    if name == "arrayOf":
        return f"list of {_type_name(t.get('value'))}"
    if name in ("shape", "exact"):
        return "dict"
    return name or "any"


def _default(prop) -> str:
    d = prop.get("defaultValue")
    if isinstance(d, dict):
        return str(d.get("value", ""))
    return "" if d is None else str(d)


def _sort(props: list[dict]) -> list[dict]:
    props.sort(key=lambda p: (p["name"] != "id", p["name"]))
    return props


def _from_metadata(mod, meta_path: Path) -> list[dict]:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    out = []
    for entry in meta.values():
        name = entry.get("displayName") or ""
        if not name or not hasattr(mod, name):
            continue
        props = [{
            "name": pname,
            "type": _type_name(p.get("type") or p.get("flowType") or p.get("tsType")),
            "required": bool(p.get("required")),
            "default": _default(p),
            "description": (p.get("description") or "").strip(),
        } for pname, p in (entry.get("props") or {}).items() if pname not in _SKIP_PROPS]
        out.append({"name": name, "description": (entry.get("description") or "").strip(),
                    "props": _sort(props)})
    out.sort(key=lambda c: c["name"])
    return out


# `- name (type; optional): description` / `- name (type; required)` /
# `- name (type; default 0): description`, description continuing on
# indented lines until the next `- ` or a blank line.
_DOC_PROP = re.compile(
    r"^\s*-\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<meta>[^)]*)\):\s*$"
)


def _doc_props(doc: str) -> dict:
    """``{prop: (type text, required, description)}`` from a Dash-style
    ``Keyword arguments:`` block — the format generated classes use and the
    format this package's hand-written classes were written to match."""
    out: dict = {}
    if not doc or "Keyword arguments:" not in doc:
        return out
    body = doc.split("Keyword arguments:", 1)[1]
    name = None
    meta = ""
    buf: list = []
    for line in body.splitlines():
        m = _DOC_PROP.match(line)
        if m:
            if name:
                out[name] = (meta, " ".join(buf).strip())
            name, meta, buf = m.group("name"), m.group("meta"), []
        elif name is not None:
            buf.append(line.strip())
    if name:
        out[name] = (meta, " ".join(buf).strip())
    # The parenthesised field is `<type>[; optional|required|default <v>]`.
    # Keep the QUALIFIER as well as the type: dropping it here is how the
    # documented default (`string; default 'md'`) silently became blank in the
    # rendered table on any class with no __init__ to fall back on.
    return {k: (mt.split(";")[0].strip(), "required" in mt, _clean(d), mt)
            for k, (mt, d) in out.items()}


def _clean(text: str) -> str:
    """Docstrings use RST double-backticks; the tables render Markdown."""
    return re.sub(r"``([^`]+)``", r"`\1`", text).strip()


def _annotation_name(ann) -> str:
    """A short, readable type for a signature annotation."""
    if ann is inspect.Parameter.empty:
        return ""
    origin = typing.get_origin(ann)
    if origin is typing.Union:
        args = [a for a in typing.get_args(ann) if a is not type(None)]  # noqa: E721
        return " | ".join(_annotation_name(a) for a in args)
    if origin in (list, dict, tuple, set):
        return origin.__name__
    return getattr(ann, "__name__", None) or str(ann).replace("typing.", "")


def _doc_default(type_text: str) -> str:
    """A docstring type field may carry the default: ``string; default 'md'``
    arrives here as the type when there is no signature to ask."""
    m = re.search(r"default\s+(.+)$", type_text or "")
    return m.group(1).strip() if m else ""


def _from_docstrings(mod) -> list[dict]:
    """One entry per class documenting props under ``Keyword arguments:``.

    THE DOCSTRING IS THE SOURCE, the signature only enriches it. A generated
    Dash class and this fork's hand-authored ones both carry the section; the
    fleet's fixture package (tests/fixtures/docstring_dash_pkg) carries it on
    a class that is not a Component subclass at all, which is the honest test
    of "read the docstring" — so the docstring decides membership and the
    ``__init__`` signature is consulted only where one exists.
    """
    out = []
    for name in getattr(mod, "__all__", None) or dir(mod):
        if name.startswith("_"):
            continue
        cls = getattr(mod, name, None)
        if not isinstance(cls, type):
            continue
        doc = inspect.getdoc(cls) or ""
        if "Keyword arguments:" not in doc:
            continue
        described = _doc_props(doc)
        try:
            sig = inspect.signature(cls.__init__)
        except (TypeError, ValueError):  # pragma: no cover
            sig = None
        if sig is None or not described or set(described) - set(sig.parameters):
            # No signature, or one that does not cover what the docstring
            # documents (the fixture's plain class): the docstring alone is
            # the record. Never drop a documented prop for lacking a
            # parameter — that is how a table silently loses rows.
            props = [{"name": pname,
                      "type": meta[0],
                      "required": meta[1],
                      "default": _doc_default(meta[3]),
                      "description": meta[2]}
                     for pname, meta in described.items()
                     if pname not in _SKIP_PROPS]
            summary = _clean(doc.split("Keyword arguments:", 1)[0].strip().split("\n\n")[0])
            out.append({"name": name, "description": summary, "props": _sort(props)})
            continue
        props = []
        for pname, param in sig.parameters.items():
            if pname in ("self", "setProps", "loading_state") or param.kind in (
                inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD
            ):
                continue
            doc_type, doc_required, description, _raw = described.get(pname, ("", False, "", ""))
            default = param.default
            has_default = default is not inspect.Parameter.empty and default is not None
            props.append({
                "name": pname,
                "type": doc_type or _annotation_name(param.annotation),
                "required": doc_required,
                "default": repr(default) if has_default and not isinstance(default, str) else (default or ""),
                "description": description,
            })
        props.sort(key=lambda p: (p["name"] != "id", p["name"]))
        summary = _clean(doc.split("Keyword arguments:", 1)[0].strip().split("\n\n")[0])
        out.append({"name": name, "description": summary, "props": props})
    out.sort(key=lambda c: c["name"])
    return out


def load_package(package: str) -> list[dict]:
    """``[{name, description, props: [{name, type, required, default, description}]}]``
    for every component the package exports, sorted by name — from
    metadata.json, else the committed extract, else the docstrings. Raises
    ImportError if the package is not installed."""
    mod = importlib.import_module(package)
    pkg_dir = Path(mod.__file__).resolve().parent
    meta_path = pkg_dir / "metadata.json"
    if meta_path.is_file():
        return _from_metadata(mod, meta_path)
    slim = pkg_dir / SLIM_METADATA
    if slim.is_file():
        data = json.loads(slim.read_text(encoding="utf-8"))
        return data["components"] if isinstance(data, dict) else data
    return _from_docstrings(mod)


def slim_generated_on(package: str) -> str | None:
    """The ``generated`` date of the committed extract — /api's lastmod. It
    moves exactly when the script that regenerates the content runs, and it
    is committed, so a Docker rebuild cannot reset it the way an mtime can."""
    try:
        mod = importlib.import_module(package)
        data = json.loads((Path(mod.__file__).resolve().parent / SLIM_METADATA).read_text(encoding="utf-8"))
        return data.get("generated") if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        return None


def load_packages(packages) -> list[dict]:
    """Every package's components, in declaration order; a missing package
    is reported as one entry with an ``error`` rather than raising — the
    page must render on a host whose extra is not installed."""
    out = []
    for pkg in packages:
        try:
            out.append({"package": pkg, "components": load_package(pkg)})
        except Exception as exc:  # noqa: BLE001
            out.append({"package": pkg, "components": [], "error": f"{type(exc).__name__}: {exc}"})
    return out


def _cell(text) -> str:
    """One Markdown table cell: no newlines, no unescaped pipes — in EVERY
    cell (a type like `a | b` broke the table as surely as a description)."""
    return str(text).replace("\n", " ").replace("|", "\\|")


def as_markdown(packages) -> str:
    """The same tables as Markdown — the page's LLMS_DOC."""
    lines = ["# API reference", ""]
    for pkg in load_packages(packages):
        lines += [f"## {pkg['package']}", ""]
        if pkg.get("error"):
            lines += [f"_not installed: {pkg['error']}_", ""]
        for c in pkg["components"]:
            lines += [f"### {c['name']}", ""]
            if c["description"]:
                lines += [c["description"], ""]
            lines += ["| prop | type | default | description |", "|---|---|---|---|"]
            for p in c["props"]:
                lines.append(f"| `{_cell(p['name'])}`{' *' if p['required'] else ''} | {_cell(p['type'])} | {_cell(p['default'])} | {_cell(p['description'])} |")
            lines.append("")
    return "\n".join(lines)
