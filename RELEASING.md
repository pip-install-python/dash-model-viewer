# Releasing `dash-model-viewer`

The checklist that gates a tag. Written for 1.0.0 — the first release from this
rebuild, and the first to go out through the automated lane at
`.github/workflows/release.yml`.

Two of these steps are **the owner's alone** and neither can be done from a
session: creating the PyPI publisher, and pushing the tag. They are marked.

---

## Before the tag

### 1. The version, in every encoding

`pyproject.toml`'s `version` is the single source. `__version__` is read from
installed metadata at import (`importlib.metadata`), never from a file in the
package — a `package-info.json` read at import time is one of the artefacts the
anti-regeneration test forbids, and it is how 0.0.1 could regenerate itself
backwards from a stale dev environment.

- [ ] `pyproject.toml` → `version = "1.0.0"`
- [ ] `CHANGELOG.md` has a `## [1.0.0]` section (the lane fails without it)
- [ ] A wheel built from this tree installs and reports `1.0.0`:

      python -m build
      python3.12 -m venv /tmp/mv-check
      /tmp/mv-check/bin/pip install dist/dash_model_viewer-1.0.0-py3-none-any.whl dash
      /tmp/mv-check/bin/python -c "import dash_model_viewer as m; print(m.__version__)"

  **Expect `1.0.0`.** In a checkout where the package is *not* installed the
  same import prints `0.0.0.dev0`. That is the documented fallback doing its
  job, not a defect — do not "fix" it.

### 2. The suites

- [ ] `pytest` — full suite green, and note the count rather than trusting a
      glance. Capture the exit code from the command, **not** through a pipe:
      `pytest -q > out.txt; echo $?`. A pipeline's status is the last command's,
      which is how a red suite gets committed over.
- [ ] `flake8` — note that `.flake8` excludes `docs/*/`, so a green there means
      those files were **not read**. `examples/` and `tests/` are linted.
- [ ] The documented examples all import and construct (13 of them).

### 3. The wheel

The fork-specific risk. This package's JavaScript is **committed, not built**:
the hand-authored shim and Google's vendored UMD bundle ship as package data.
A wheel missing them is dead on arrival, and a version cannot be re-uploaded to
replace it.

- [ ] `unzip -l dist/*.whl` shows `dash_model_viewer/vendor/model-viewer-umd.min.js`,
      `dash_model_viewer/vendor/model-viewer-LICENSE`, and
      `dash_model_viewer/dash_model_viewer.js`
- [ ] Nothing outside `dash_model_viewer/` and its dist-info is in the wheel —
      the documentation site must not leak in

Both are asserted by the release lane's `build` job and by `ci.yml`'s
`package-matrix`, deliberately in both places: CI proves it for a commit, the
lane proves it for the artifact actually being published.

### 4. The manual walk

Automated checks prove the load pipeline reaches Python. **Nothing proves a
human sees a rendered model** — a backgrounded browser tab never renders, by
design, because `model-viewer` waits for visibility. The walk is not optional
and is not replaceable by a test.

- [ ] The walk is completed on a desktop browser in a **foreground** tab
- [ ] The AR section is completed on a **real phone**, and on Android
      specifically AR is confirmed to enter via **WebXR** — a fallback to
      scene-viewer would mask the exact regression the 1.0.0 AR fix prevents
- [ ] `examples/manual_walk.py` covers the props no page exercises and the
      error path

### 5. The PyPI publisher — **the owner's, on pypi.org**

Trusted publishing stores no token; PyPI verifies a short-lived OIDC token
minted by GitHub for this repo, workflow and environment. For this project the
publisher must be **created**, not confirmed: `dash-model-viewer` has a 0.0.1
from 2025-04-17, uploaded before trusted publishing was set up here.

    pypi.org -> dash-model-viewer -> Publishing -> Add a new pending publisher
      Owner:            pip-install-python
      Repository:       dash-model-viewer
      Workflow name:    release.yml
      Environment name: pypi

- [ ] The pending publisher exists

Until it does, the `publish` job fails with an opaque 403 and nothing uploads.

---

## The tag — **the owner's word**

Nothing else in this document publishes anything. Pushing a `v*` tag is what
starts the lane, and it is the owner's to push.

    git tag v1.0.0
    git push origin v1.0.0

The lane then: verifies the tag matches `pyproject` and that the CHANGELOG
documents it → builds and `twine check`s → runs the package's suites against
the built wheel → asserts the wheel's contents → publishes by OIDC → opens a
GitHub Release with that version's CHANGELOG section as its body.

Concurrency is `cancel-in-progress: false` on purpose. A half-cancelled publish
is the one state worth avoiding, because a version uploads exactly once.

### A rehearsal, if wanted

`workflow_dispatch` with `dry_run` (default true) publishes to **TestPyPI**
instead. It needs its own pending publisher on test.pypi.org, configured the
same way.

---

## After the tag

- [ ] `pip install dash-model-viewer` in a fresh venv resolves **1.0.0**
- [ ] The **landing page's** code block, with `src` pointed at
      `https://modelviewer.dev/shared-assets/models/Astronaut.glb`, runs against
      that install and renders in a foreground tab

  Use the landing page's block, **not** the quick-start example. The
  quick-start example is a page fragment: it defines `component` rather than an
  app and imports `lib.demo_models`, which is documentation-site code and is not
  in the wheel. It cannot run standalone and never could.

- [ ] The catalogue page at `2plot.dev/pip/dash_model_viewer` is regenerated —
      it currently teaches the 0.0.1 API (`DashModelViewer`, camelCase props,
      an unpinned install line), which was correct while 0.0.1 was what `pip`
      served and is wrong the moment 1.0.0 ships
- [ ] `/healthz` on the satellite still reports the expected build
