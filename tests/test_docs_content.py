"""Static checks on docs/ — the failures that only surface at import time.

Everything here is cheap and runs without booting the app, which makes it the
first thing to fail when a new documentation page is wrong.
"""

from __future__ import annotations

import importlib
import re
import sys

import frontmatter
import pytest

from conftest import REPO_ROOT
from lib.directives.headings import plain_text, slugify

DOCS = sorted((REPO_ROOT / "docs").glob("**/*.md"))
EXEC_DIRECTIVE = re.compile(r"^\.\. exec::(.+?)$", re.MULTILINE)
SOURCE_DIRECTIVE = re.compile(r"^\.\. source::(.+?)$", re.MULTILINE)
CODE_FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
REQUIRED_FRONTMATTER = ("name", "description", "endpoint")


def live_directives(content: str) -> str:
    """Content with fenced code blocks removed.

    Several pages *document* directive syntax, so `.. exec::docs.my-component.example`
    appears inside ```markdown fences as an illustration. Those are examples,
    not references — resolving them would fail by design. This is the same
    fence-awareness the 2.1 prose renderer applies when it strips directives.
    """
    return CODE_FENCE.sub("", content)


def test_docs_directory_is_not_empty():
    assert DOCS, "no markdown files found under docs/"


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_frontmatter_is_complete(path):
    metadata, _content = frontmatter.parse(path.read_text())
    missing = [key for key in REQUIRED_FRONTMATTER if not metadata.get(key)]
    assert not missing, f"{path.name} is missing frontmatter keys: {missing}"
    assert metadata["endpoint"].startswith("/"), "endpoint must be an absolute path"


def test_endpoints_are_unique():
    seen: dict[str, str] = {}
    for path in DOCS:
        metadata, _ = frontmatter.parse(path.read_text())
        endpoint = metadata.get("endpoint")
        assert endpoint not in seen, (
            f"{path.name} and {seen[endpoint]} both register {endpoint}; the second "
            "registration silently wins and one page becomes unreachable"
        )
        seen[endpoint] = path.name


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_exec_directives_point_at_importable_modules(path):
    _metadata, content = frontmatter.parse(path.read_text())
    for match in EXEC_DIRECTIVE.finditer(live_directives(content)):
        module = match.group(1).strip().split()[0]
        try:
            importlib.import_module(module)
        except Exception as exc:  # noqa: BLE001 - the failure is the point
            pytest.fail(f"{path.name}: `.. exec::{module}` failed to import: {exc!r}")


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_source_directives_point_at_real_files(path):
    _metadata, content = frontmatter.parse(path.read_text())
    for match in SOURCE_DIRECTIVE.finditer(live_directives(content)):
        target = REPO_ROOT / match.group(1).strip()
        assert target.is_file(), f"{path.name}: `.. source::` target does not exist: {target}"


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_headings_render_and_match_their_toc_anchors(path, app_module):
    """One backtick in a heading used to take the whole site down at startup.

    markdown2dash slugged only the first inline token for the heading id while
    the toc directive slugged the raw markdown, so formatted headings either
    crashed the renderer or produced an anchor pointing at nothing. Both sides
    now go through `slugify`; this asserts they still agree.
    """
    # via app_module: importing pages.markdown standalone raises PageError,
    # because registering a page requires an instantiated app.
    parse = sys.modules["pages.markdown"].parse

    _metadata, content = frontmatter.parse(path.read_text())
    layout = parse(content)  # raises if a heading breaks the renderer

    # className="m2d-heading" is what the renderer stamps on headings it
    # generated. Without that filter this also picks up dmc.Title components
    # inside `.. exec::` examples, whose ids are the example's own and have
    # nothing to do with anchors.
    rendered = {
        component.id: plain_text(component.children)
        for component in _walk(layout)
        if type(component).__name__ == "Title"
        and getattr(component, "className", None) == "m2d-heading"
        and getattr(component, "id", None)
    }
    assert rendered, f"{path.name}: no markdown headings found to check"
    for heading_id, text in rendered.items():
        assert heading_id == slugify(text), (
            f"{path.name}: heading {text!r} has id {heading_id!r}, but its TOC "
            f"anchor would be {slugify(text)!r}"
        )


def _walk(node):
    """Every component in a rendered layout tree."""
    if isinstance(node, (list, tuple)):
        for child in node:
            yield from _walk(child)
        return
    if isinstance(node, str) or node is None:
        return
    yield node
    children = getattr(node, "children", None)
    if children is not None:
        yield from _walk(children)
