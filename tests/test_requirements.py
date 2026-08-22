"""Every third-party module the SITE imports at runtime must be declared.

The failure this exists for is specific and it took the site down on its first
deploy: `lib/relief.py` imports Pillow, `docs/image-to-3d/relief_page.py`
calls it at module import, and Pillow was not in requirements.txt. Every
machine it was tested on already had Pillow — it arrives with half the
scientific stack — so the suite was green, the app booted locally, and the
gap appeared only in a clean container, as `ModuleNotFoundError: No module
named 'PIL'` with all ten pages down behind it.

The container job in CI does catch this, by building a clean image and
booting it. That is the right check and it is also the slow one, several
minutes behind a push, and Render's autoDeploy does not wait for it. This
test is the fast copy: it reads the imports and the requirements file and
compares them, in milliseconds, with no network and no Docker.

Scope note: `scripts/` is deliberately NOT covered. Those are build-time
tools (make_brand_assets, make_social_card), they guard their imports and
exit with an instruction, and they are never imported by the running site.
That distinction is the whole reason Pillow was left out in the first place —
the reasoning was right for scripts/ and wrong the moment lib/ needed it.
"""
from __future__ import annotations

import ast
import re
import sys
from importlib.metadata import packages_distributions
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# The directories that are imported by a running site. scripts/ is excluded
# on purpose — see the module docstring.
RUNTIME_DIRS = ("lib", "pages", "components", "docs")

# First-party: importable because of the repo layout, never from a wheel.
FIRST_PARTY = {"lib", "pages", "components", "docs", "conftest",
               "dash_model_viewer", "run", "tests"}


def _requirement_names() -> set[str]:
    """Distribution names declared in requirements.txt, normalised.

    Handles the three shapes this file actually uses: a plain pin, an extras
    pin (`dash-improve-my-llms[flask]>=2.6.0`), and the vendored local path
    (`./vendor/dash_clerk_auth-1.0.5.tar.gz`).
    """
    names: set[str] = set()
    for raw in (REPO / "requirements.txt").read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith(("./", "../", "/")):
            stem = Path(line).name
            m = re.match(r"([A-Za-z0-9._-]+?)-\d", stem)
            if m:
                names.add(_norm(m.group(1)))
            continue
        m = re.match(r"[A-Za-z0-9._-]+", line)
        if m:
            names.add(_norm(m.group(0)))
    return names


# Installed deliberately, but NOT from requirements.txt. markdown2dash 0.1.2
# declares `gunicorn>=21.2.0,<22.0.0` — a markdown parser pinning a WSGI
# server, directly against the CVE-driven gunicorn>=23 floor. pip cannot
# resolve both, so it is installed on its own line with --no-deps and its real
# dependencies are listed in requirements.txt instead.
#
# This is an exemption that has to be EARNED, not asserted: the test below
# checks that every install path actually carries the extra command. An
# exemption nobody verifies is just a hole with a comment over it.
# The optional backends. DASH_BACKEND picks ONE at boot (flask by default);
# the other two are never imported, so their packages are not installed and
# must not be required. requirements.txt carries them as COMMENTED lines —
# deliberately visible, deliberately off.
#
# `starlette` has no line of its own because it arrives with fastapi.
#
# This exemption is narrower than it looks, and the tests below hold it to
# that: a module here is exempt from being DECLARED, not from being GATED.
# Two files import fastapi/starlette at module level; they are safe only
# because run.py imports THEM from inside `if BACKEND == "fastapi"`. Move
# either import to run.py's top level and every Flask deploy dies on boot —
# which is the Pillow failure again, wearing a different module name.
OPTIONAL_BACKENDS = {
    "fastapi": "fastapi",
    "starlette": "fastapi",   # transitive
    "quart": "quart",
}


OUT_OF_BAND = {
    "markdown2dash": (
        "Dockerfile",
        ".github/workflows/ci.yml",
        "scripts/dev.sh",
    ),
}


def _norm(name: str) -> str:
    """PEP 503 normalisation: Pillow, pillow and PIL's dist all compare equal."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _runtime_modules() -> dict[str, list[str]]:
    """Top-level module name -> the files that import it."""
    found: dict[str, list[str]] = {}
    for directory in RUNTIME_DIRS:
        for path in sorted((REPO / directory).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    # level > 0 is a relative import: first-party by definition.
                    if node.level:
                        continue
                    mods = [node.module or ""]
                else:
                    continue
                for mod in mods:
                    top = mod.split(".")[0]
                    if not top or top in FIRST_PARTY:
                        continue
                    if top in sys.stdlib_module_names:
                        continue
                    found.setdefault(top, []).append(
                        str(path.relative_to(REPO))
                    )
    return found


def test_every_runtime_third_party_import_is_in_requirements():
    declared = _requirement_names()
    mapping = packages_distributions()
    missing: list[str] = []

    for module, importers in sorted(_runtime_modules().items()):
        dists = {_norm(d) for d in mapping.get(module, [])}
        if not dists:
            # Installed but unmappable, or not installed at all. Either way
            # this test cannot judge it; the container job still can.
            continue
        if dists & declared:
            continue
        if module in OUT_OF_BAND or module in OPTIONAL_BACKENDS:
            continue
        missing.append(
            f"  `import {module}` (provided by "
            f"{', '.join(sorted(dists))}) — imported in "
            f"{', '.join(sorted(set(importers))[:3])}"
        )

    assert not missing, (
        "These modules are imported by the running site but no distribution "
        "providing them is declared in requirements.txt:\n"
        + "\n".join(missing)
        + "\n\nThey work here only because this environment happens to have "
        "them. A clean container will fail to boot — and because "
        "docs pages are imported during app construction, one missing "
        "module takes every page down, not just its own."
    )


def test_pillow_specifically_is_declared():
    """The regression that produced this file, pinned by name.

    The general test above would catch it, but only while Pillow is still
    importable in the test environment. This one states the fact directly so
    the reason survives even if the mapping does not.
    """
    assert "pillow" in _requirement_names(), (
        "Pillow is missing from requirements.txt. lib/relief.py needs it at "
        "runtime and docs/image-to-3d/relief_page.py carves at import, so its "
        "absence is a site-wide boot failure, not a degraded page."
    )


@pytest.mark.parametrize("floor", ["clerk-backend-api", "cryptography"])
def test_clerk_security_floors_are_declared(floor):
    """dash-clerk-auth's own range allows clerk-backend-api 5.x, which caps
    cryptography below the fixes for four advisories. The floors have to be
    asserted here, not merely permitted by the package."""
    assert _norm(floor) in _requirement_names()


@pytest.mark.parametrize("module,install_paths", sorted(OUT_OF_BAND.items()))
def test_out_of_band_installs_reach_every_path(module, install_paths):
    """A module exempted from requirements.txt must be installed everywhere.

    requirements.txt is the one file people read to answer "what does this
    need". Anything deliberately kept out of it is invisible, so the install
    command has to exist in EVERY path that builds this site — miss one and
    that path boots without the module and takes the whole app down, which is
    the same failure mode Pillow just demonstrated.

    render.yaml is deliberately not in the list: this service is
    `runtime: docker`, so it has no buildCommand and the Dockerfile is its
    install path. If it ever moves back to a native runtime, its buildCommand
    joins this list.
    """
    for rel in install_paths:
        text = (REPO / rel).read_text()
        assert f"--no-deps {module}==" in text, (
            f"{rel} does not install {module} with --no-deps. It is exempt "
            f"from requirements.txt, so this is the only thing putting it in "
            f"that environment."
        )


@pytest.mark.parametrize("module,installer", sorted(OPTIONAL_BACKENDS.items()))
def test_optional_backends_are_documented_in_requirements(module, installer):
    """Exempt from being required, not from being written down.

    An optional dependency that appears nowhere in requirements.txt is
    indistinguishable from a forgotten one. Each must appear as a commented
    line naming the distribution that installs it, so the file still answers
    "what does the fastapi backend need" without reading the code.
    """
    text = (REPO / "requirements.txt").read_text()
    assert re.search(rf"^#\s*{re.escape(installer)}\b", text, re.M), (
        f"{installer} is not documented as a commented optional line in "
        f"requirements.txt, but lib/ imports `{module}`."
    )


def test_optional_backend_imports_never_reach_the_default_boot():
    """The gate that makes the exemption above safe.

    lib/asgi_routes.py and lib/asgi_middleware.py import fastapi/starlette at
    module level and are perfectly correct — because run.py only imports them
    inside `if BACKEND == "fastapi"`. A top-level (column-zero) import of
    either in run.py would make every Flask deploy fail to boot on a package
    that requirements.txt deliberately does not install.
    """
    offenders = [
        f"{path.name} imports {module} at module level"
        for path in sorted((REPO / "lib").glob("*.py"))
        for module in OPTIONAL_BACKENDS
        if re.search(rf"^(from|import) {module}\b", path.read_text(), re.M)
    ]
    assert offenders, (
        "Expected at least one module-level optional-backend import — if "
        "these moved, this test is now checking nothing and should be "
        "rewritten against wherever they went."
    )

    gated_modules = {
        path.stem
        for path in sorted((REPO / "lib").glob("*.py"))
        for module in OPTIONAL_BACKENDS
        if re.search(rf"^(from|import) {module}\b", path.read_text(), re.M)
    }

    run_py = (REPO / "run.py").read_text()
    for stem in sorted(gated_modules):
        top_level = re.search(rf"^from lib\.{stem} import", run_py, re.M)
        assert not top_level, (
            f"run.py imports lib.{stem} at the TOP LEVEL. That module imports "
            f"an optional backend package which requirements.txt does not "
            f"install, so every default (flask) deploy would fail to boot. "
            f"Keep it inside the `if BACKEND == ...` branch."
        )
