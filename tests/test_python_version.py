"""One fleet Python — image, matrix, render.yaml and the wire must agree.

Found by the ops seat reading the tree, not a report (2026-08-25): the
template's Dockerfile said `python:3.11.8-slim` — a PATCH pin, so the image
never received a 3.11.x security release — while the CI matrix said 3.12 and
render.yaml said 3.12.0. Three declared Pythons, the docker boot/battery
testing an interpreter the matrix never ran, and nothing on the wire able to
contradict any of them. These pins hold every encoding to ONE minor, sourced
from the Dockerfile's FROM tag; /healthz's `python` field plus the
`python_matches_declared` battery check (scripts/network_smoke.py) hold the
serving host to the same one.

What is deliberately NOT here: no comparison of the RUNNING interpreter to
the fleet minor — the suite legitimately runs on the adjacent window legs
(the matrix's 3.13/3.12 rows), where that assertion would be false by
design. Image-vs-declaration is the battery's job, against a host.

FORK ADAPTATION (dash-model-viewer, 2026-08-26). The template's version of
this file assumes ONE matrix in ci.yml and asserts against every `python:`
line in the file. This repo has TWO lanes, because it is both a docs site and
a published PyPI package:

    test            the SITE. Its interpreter is a deploy artifact, so it is
                    the fleet Python and the window around it.
    package-matrix  the WHEEL, across `requires-python = ">=3.9"`. Those
                    numbers encode what dash_model_viewer supports for its
                    users, which is a different fact from what this site
                    deploys on, and holding them to the fleet minor would
                    delete the compatibility promise rather than sync it.

So the pins below are JOB-SCOPED rather than file-scoped. The exemption is
earned, not asserted: `test_the_package_lane_still_covers_its_declared_range`
holds the exempt lane to its own contract, and
`test_the_package_lane_tests_the_fleet_python_too` keeps it honest about the
interpreter this site installs the wheel on. An exemption nobody checks is a
hole with a comment over it.
"""
from __future__ import annotations

import re

import yaml

from conftest import REPO_ROOT

CI = ".github/workflows/ci.yml"
CD = ".github/workflows/cd.yml"


def _fleet_minor() -> str:
    """The single source: the Dockerfile's FROM tag."""
    for line in (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines():
        m = re.match(r"FROM\s+python:(\S+)", line)
        if m:
            return m.group(1)
    raise AssertionError("Dockerfile has no `FROM python:` line")


def _uncommented(path) -> list[str]:
    return [
        ln for ln in (REPO_ROOT / path).read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("#")
    ]


def _jobs(path) -> dict:
    return yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))["jobs"]


def _matrix(job) -> dict:
    return (job.get("strategy") or {}).get("matrix") or {}


def _site_job(jobs) -> dict:
    """The lane whose interpreter is a deploy artifact: it varies `backend`,
    because backends are a property of the running site, never of the wheel."""
    named = [j for j in jobs.values() if "backend" in _matrix(j)]
    assert len(named) == 1, (
        f"expected exactly one site lane in {CI}, found {len(named)} — this "
        "file's job-scoping was written against a two-lane ci.yml and needs "
        "rewriting against whatever it is now"
    )
    return named[0]


def _package_job(jobs) -> dict:
    named = [j for j in jobs.values()
             if "dash" in _matrix(j) and "backend" not in _matrix(j)]
    assert len(named) == 1, f"expected exactly one package lane in {CI}"
    return named[0]


def _literal_pins(job) -> list[str]:
    """Literal `python-version:` pins in a job's steps — `${{ matrix.python }}`
    is not one."""
    return [
        step["with"]["python-version"]
        for step in job.get("steps", [])
        if isinstance(step.get("with"), dict)
        and re.fullmatch(r"[\d.]+", str(step["with"].get("python-version", "")))
    ]


def test_dockerfile_tag_is_minor_only():
    """The patch pin IS the security bug: `3.11.8-slim` never receives a
    3.11.x fix release. The minor tag tracks them through Docker Hub."""
    tag = _fleet_minor()
    assert re.fullmatch(r"\d+\.\d+-slim", tag), (
        f"Dockerfile FROM tag is {tag!r} — must be a MINOR tag "
        "(python:X.Y-slim), never a patch pin"
    )


def test_render_yaml_agrees_with_the_image():
    """Render's PYTHON_VERSION takes a full X.Y.Z (its encoding, not ours) —
    the MINOR must be the fleet Python. The patch there needs a human bump
    now and then; the minor drifting is the class this file exists for."""
    minor = _fleet_minor().removesuffix("-slim")
    lines = _uncommented("render.yaml")
    value = None
    for i, ln in enumerate(lines):
        if re.match(r"\s*- key: PYTHON_VERSION$", ln):
            m = re.search(r'value:\s*"([^"]+)"', lines[i + 1])
            value = m and m.group(1)
            break
    assert value, "render.yaml declares no PYTHON_VERSION"
    assert re.fullmatch(r"\d+\.\d+\.\d+", value), (
        f"PYTHON_VERSION {value!r} — Render requires full X.Y.Z"
    )
    assert value.startswith(minor + "."), (
        f"render.yaml PYTHON_VERSION {value} vs image python:{minor}-slim — "
        "the native-runtime lane and the image lane disagree"
    )


def test_site_matrix_main_agrees_with_the_image():
    minor = _fleet_minor().removesuffix("-slim")
    main = _matrix(_site_job(_jobs(CI))).get("python")
    assert main == [minor], (
        f"the site lane's matrix main is {main} vs image python:{minor}-slim"
    )


def test_the_whole_repo_lint_and_audit_jobs_run_the_fleet_python():
    """Every job that is NOT one of the two matrices pins a literal version.
    Those jobs read the repo as a whole (flake8, pip-audit), so there is no
    second contract to respect — they are the fleet Python or they are drift.
    """
    minor = _fleet_minor().removesuffix("-slim")
    jobs = _jobs(CI)
    site, package = _site_job(jobs), _package_job(jobs)
    literals = [v for job in jobs.values() if job not in (site, package)
                for v in _literal_pins(job)]
    assert literals, (
        f"no literal python-version pins found outside the matrices in {CI} — "
        "this test is now checking nothing"
    )
    assert set(literals) == {minor}, (
        f"{CI} whole-repo jobs pin {sorted(set(literals))}, image is "
        f"python:{minor}-slim"
    )

    cd_literals = [v for job in _jobs(CD).values() for v in _literal_pins(job)]
    assert cd_literals and set(cd_literals) == {minor}, (
        f"{CD} pins {sorted(set(cd_literals))}, image is python:{minor}-slim"
    )


def test_site_matrix_legs_are_the_adjacent_minors():
    """The compat window stays three wide: the include legs on the default
    backend are X.Y-1 and X.Y-2 (or X.Y+1 once it exists). The dash-bottom
    rows pin their own python and sit inside the same window — they vary the
    dash axis, not the python axis."""
    major, y = (int(p) for p in _fleet_minor().removesuffix("-slim").split("."))
    allowed = {f"{major}.{y}", f"{major}.{y - 1}", f"{major}.{y - 2}",
               f"{major}.{y + 1}"}
    legs = [str(row["python"])
            for row in _matrix(_site_job(_jobs(CI))).get("include", [])]
    assert legs, "the site matrix has no include legs — the window collapsed"
    outside = [leg for leg in legs if leg not in allowed]
    assert not outside, (
        f"site matrix legs {outside} fall outside the three-wide window "
        f"around {major}.{y}"
    )


def test_the_package_lane_still_covers_its_declared_range():
    """The earned half of the package lane's exemption.

    It is exempt from the fleet minor because it tests the WHEEL, not the
    site — so it owes the wheel's own contract instead: the endpoints of
    `requires-python` both get a run. Without this, "exempt" would quietly
    mean "unchecked", and the floor could rot to a number nothing exercises.
    """
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'requires-python\s*=\s*">=([\d.]+)"', pyproject)
    assert m, "pyproject.toml declares no requires-python floor"
    floor = m.group(1)

    matrix = _matrix(_package_job(_jobs(CI)))
    covered = {str(matrix["python"][0])} | {
        str(row["python"]) for row in matrix.get("include", [])
    }
    assert floor in covered, (
        f"pyproject claims Python >={floor} but the package matrix never runs "
        f"it (covers {sorted(covered)}) — an untested floor is a guess"
    )


def test_the_package_lane_tests_the_fleet_python_too():
    """The site installs THIS wheel (`pip install --no-deps .` in the
    Dockerfile) and serves it on the fleet Python. A wheel lane that never
    runs the fleet minor would let the docker boot be the first thing to
    discover a 3.14 incompatibility — on production's first pull.
    """
    minor = _fleet_minor().removesuffix("-slim")
    matrix = _matrix(_package_job(_jobs(CI)))
    covered = {str(matrix["python"][0])} | {
        str(row["python"]) for row in matrix.get("include", [])
    }
    assert minor in covered, (
        f"the package matrix never builds the wheel on the fleet Python "
        f"{minor} (covers {sorted(covered)}) — the docker boot would be the "
        "first check, and that runs after the wheel is already published"
    )


def test_pyproject_claims_the_fleet_python():
    """Trove classifiers are the wheel's public promise. This site proves
    3.14 in CI on every push; claiming only through 3.13 would understate a
    fact the repo already establishes."""
    minor = _fleet_minor().removesuffix("-slim")
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f"Programming Language :: Python :: {minor}" in pyproject, (
        f"pyproject.toml has no classifier for the fleet Python {minor}, but "
        "CI builds and installs the wheel on it"
    )
