#!/usr/bin/env python3
"""Distil a component package's react-docgen metadata.json to the committed
extract /api renders from (1.6.41; leaflet's finding).

WHY: in a component REPO, `<package>/metadata.json` can be a multi-megabyte
build artifact that is .gitignored and excluded from the wheel — a build
INPUT, not a runtime file. The host clones the repo and never has it, so
/api passes every local check and renders EMPTY in production. This writes
`<package>/api_metadata.json` in `lib.api_reference.load_package`'s output
shape (about 1% of the size), which IS committed; `load_package` prefers
metadata.json when present, so a developer who just rebuilt sees new props
immediately, and everyone else gets this file. `generated` is /api's
sitemap lastmod: written here, by the thing that regenerates the content,
so the date and the content move together.

RUN whenever a component's props change:

    python scripts/build_api_metadata.py            # API_PACKAGES[0]
    python scripts/build_api_metadata.py my_package  # or name it
    git add <package>/api_metadata.json
"""
from __future__ import annotations

import importlib
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from lib.api_reference import SLIM_METADATA, _from_docstrings, _from_metadata  # noqa: E402


def build(package: str) -> Path:
    """THIS FORK READS DOCSTRINGS, not react-docgen.

    The template's version requires `<package>/metadata.json` and exits if it
    is missing, because on a generated component package that file is the
    build artifact. `dash_model_viewer` is hook-based since 1.0.0: there is no
    generator and no metadata.json, and `tests/test_no_regeneration.py` fails
    if one ever appears. So the source here is the same one `/api` renders
    from — the classes' docstrings plus their `__init__` signatures — and this
    script's job is only to STAMP it with a committed date the sitemap can
    use. Where the item and this tree disagree, the tree wins (DIVERGENCES 12).
    """
    mod = importlib.import_module(package)
    pkg_dir = Path(mod.__file__).resolve().parent
    source = pkg_dir / "metadata.json"
    if source.is_file():
        components = _from_metadata(mod, source)
        origin = str(source)
    else:
        components = _from_docstrings(mod)
        origin = f"{package} docstrings + __init__ signatures"
    if not components:
        raise SystemExit(f"{origin} parsed to zero components — refusing to write an empty extract.")
    out = pkg_dir / SLIM_METADATA
    previous = {}
    if out.is_file():
        try:
            previous = json.loads(out.read_text(encoding="utf-8"))
        except ValueError:
            previous = {}
        if not isinstance(previous, dict):
            previous = {}
    unchanged = previous.get("components") == components
    generated = previous.get("generated") if unchanged else date.today().isoformat()
    out.write_text(json.dumps({"generated": generated, "components": components},
                              indent=1, sort_keys=True) + "\n", encoding="utf-8")
    props = sum(len(c["props"]) for c in components)
    print(f"{out}: {len(components)} components, {props} props, "
          f"{out.stat().st_size / 1024:.0f} KB (from {origin}); "
          f"generated {generated}{' (unchanged)' if unchanged else ''}")
    return out


if __name__ == "__main__":
    if len(sys.argv) > 1:
        pkg = sys.argv[1]
    else:
        from lib.constants import API_PACKAGES

        if not API_PACKAGES:
            raise SystemExit("API_PACKAGES is empty and no package was named.")
        pkg = API_PACKAGES[0]
    build(pkg)
