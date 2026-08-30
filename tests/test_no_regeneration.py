"""Structural guards against regenerating the package backwards.

0.0.1 could regenerate its own Python from React source. A stale dev
environment was enough to make that regeneration produce something *older* in
style than what PyPI already served — the local tree's generated
``DashModelViewer.py`` came from dash 2.18.2.

"Remember not to run the build" is not a guard. These are.
"""

from __future__ import annotations

import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
PKG = REPO / "dash_model_viewer"

# Directories that legitimately contain third-party or throwaway content.
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "build",
             "dist", ".idea", ".pytest_cache", "assets", "usage_tests",
             # tests/fixtures holds a FAKE Dash component package — a
             # metadata.json written by hand so lib/api_reference's
             # metadata.json path stays exercised on a repo whose own package
             # deliberately has none. It is an input to a test, never an
             # artifact of a generator, and this guard is about the latter.
             "fixtures"}


def _walk(root: pathlib.Path):
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            yield path


def test_no_package_json():
    """No package.json means no `dash-generate-components` to run."""
    offenders = [p for p in _walk(REPO) if p.name == "package.json"]
    assert not offenders, f"package.json is back: {offenders}"


def test_no_generator_config():
    offenders = [
        p
        for p in _walk(REPO)
        if p.name
        in {
            "package-lock.json",
            "package-info.json",
            "metadata.json",
            "webpack.config.js",
            "webpack.serve.config.js",
            ".babelrc",
        }
    ]
    assert not offenders, f"generator toolchain is back: {offenders}"


def test_no_auto_generated_banner():
    """No file may claim to be generated. The bundle is the source."""
    # Split so this file does not match its own check.
    banner = "AUTO GENERATED " + "FILE"
    offenders = []
    for path in _walk(REPO):
        if path.suffix not in {".py", ".js", ".json", ".R", ".jl"}:
            continue
        # The vendored upstream bundle is Google's build product, not ours.
        if PKG / "vendor" in path.parents:
            continue
        try:
            if banner in path.read_text(encoding="utf-8", errors="replace"):
                offenders.append(path)
        except OSError:  # pragma: no cover
            continue
    assert not offenders, f"generated files present: {offenders}"


def test_retired_filename_stays_retired():
    """A stale DashModelViewer.py must not be able to shadow _components.py."""
    offenders = [p for p in _walk(REPO) if p.name == "DashModelViewer.py"]
    assert not offenders, f"retired module is back: {offenders}"


def test_no_r_or_julia_bindings():
    offenders = [
        p
        for p in _walk(REPO)
        if p.name in {"NAMESPACE", "DESCRIPTION", "Project.toml", ".Rbuildignore"}
    ]
    assert not offenders, f"generated language bindings are back: {offenders}"


def test_version_comes_from_installed_metadata():
    """`__version__` must not be read out of a JSON file at import time."""
    import dash_model_viewer

    assert isinstance(dash_model_viewer.__version__, str)
    assert dash_model_viewer.__version__

    try:
        from importlib.metadata import version
    except ImportError:  # pragma: no cover
        pytest.skip("importlib.metadata unavailable")

    try:
        installed = version("dash-model-viewer")
    except Exception:  # noqa: BLE001 - PackageNotFoundError and friends
        pytest.skip("package not installed; running from a source checkout")

    assert dash_model_viewer.__version__ == installed
