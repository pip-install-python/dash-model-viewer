"""Component prop tables from an installed Dash component package (1.6.38).

A Dash component package ships ``metadata.json`` next to its ``__init__``
(react-docgen output: one entry per component source file with
``displayName`` and ``props`` → ``{type, required, description,
defaultValue}``), and every generated component class carries the same
props in its docstring. ``metadata.json`` is the one machine-readable
source, so this reads it; the classes exist in the package namespace and
are used only to confirm a component is exported. (The drop named
``_prop_names``; Dash 4 no longer sets it on generated classes — the
docstring and metadata.json are what remain.)

THIS FORK ADDS THE SECOND SOURCE. `dash_model_viewer` is hook-based since
1.0.0: there is no generator, no build, and deliberately no
``metadata.json`` — ``tests/test_no_regeneration.py`` fails if one ever
reappears, and ``.claude/ARCHITECTURE.md`` is why. Its components are
hand-authored Python classes whose docstrings carry the SAME
``Keyword arguments:`` prop list a generated class carries, and whose
``__init__`` carries real annotations and defaults. So when a package
ships no metadata.json, this reads the docstring for the descriptions and
the signature for type, default and required — the same four columns, from
the sources this package actually has. The contract is one table per
component; metadata.json is a mechanism, not the contract.
"""
from __future__ import annotations

import importlib
import inspect
import json
import re
import typing
from pathlib import Path


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


def load_package(package: str) -> list[dict]:
    """``[{name, description, props: [{name, type, required, default, description}]}]``
    for every component the package exports, sorted by name. Raises
    ImportError if the package is not installed; returns [] if it ships no
    metadata.json (not a Dash component package)."""
    mod = importlib.import_module(package)
    meta_path = Path(mod.__file__).resolve().parent / "metadata.json"
    if not meta_path.is_file():
        return _load_from_python(mod)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    out = []
    for entry in meta.values():
        name = entry.get("displayName") or ""
        if not name or not hasattr(mod, name):
            continue
        props = []
        for pname, p in (entry.get("props") or {}).items():
            if pname in ("setProps", "loading_state"):
                continue
            props.append({
                "name": pname,
                "type": _type_name(p.get("type") or p.get("flowType") or p.get("tsType")),
                "required": bool(p.get("required")),
                "default": _default(p),
                "description": (p.get("description") or "").strip(),
            })
        props.sort(key=lambda p: (p["name"] != "id", p["name"]))
        out.append({"name": name, "description": (entry.get("description") or "").strip(), "props": props})
    out.sort(key=lambda c: c["name"])
    return out


# --------------------------------------------------------------------------
# The no-metadata.json path — hand-authored Dash components (this fork).
# --------------------------------------------------------------------------

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
    return {k: (mt.split(";")[0].strip(), "required" in mt, _clean(d))
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


def _load_from_python(mod) -> list[dict]:
    """One entry per exported Component subclass, props from the class's
    ``__init__`` signature and its docstring."""
    try:
        from dash.development.base_component import Component
    except Exception:  # pragma: no cover — Dash is a hard dependency
        return []

    out = []
    for name in getattr(mod, "__all__", None) or dir(mod):
        cls = getattr(mod, name, None)
        if not (isinstance(cls, type) and issubclass(cls, Component) and cls is not Component):
            continue
        doc = inspect.getdoc(cls) or ""
        described = _doc_props(doc)
        try:
            sig = inspect.signature(cls.__init__)
        except (TypeError, ValueError):  # pragma: no cover
            continue
        props = []
        for pname, param in sig.parameters.items():
            if pname in ("self", "setProps", "loading_state") or param.kind in (
                inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD
            ):
                continue
            doc_type, doc_required, description = described.get(pname, ("", False, ""))
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
                # Escape the pipe in EVERY cell, not just the description: a
                # union type renders as `string | dict` and an enum default as
                # `'auto' | 'fixed'`, and an unescaped pipe silently splits the
                # row into extra columns. The template escapes the description
                # only, which is invisible until a package has a union-typed
                # prop — this one has several (reported to the seat).
                def cell(value):
                    return str(value).replace("\n", " ").replace("|", "\\|")

                lines.append(
                    f"| `{p['name']}`{' *' if p['required'] else ''} "
                    f"| {cell(p['type'])} | {cell(p['default'])} | {cell(p['description'])} |"
                )
            lines.append("")
    return "\n".join(lines)
