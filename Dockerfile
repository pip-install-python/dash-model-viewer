# MINOR tag on purpose — never a patch pin. This line and render.yaml's
# PYTHON_VERSION have agreed since the gate-wave pass (the argument was and
# remains: same base here as the service, or the gate is testing something
# else), but they agreed on 3.12 while the fleet moved to 3.14, and a
# `3.X.Y-slim` pin would additionally have starved the image of 3.X security
# releases — the minor tag tracks those through Docker Hub. 3.14 is the ONE
# fleet Python, decided on evidence (template 1.6.27: full suite plus the
# docker boot/battery green on python:3.14-slim with dash 4.4.1, dimll
# >=2.7.1 and cryptography >=50 all importing). tests/test_python_version.py
# pins that this tag, the CI matrix main and render.yaml all agree, and
# /healthz reports the serving interpreter so the wire can contradict a
# stale image rather than inheriting its claim.
FROM python:3.14-slim

# Unbuffered stdout, or none of the app's print() diagnostics reliably reach
# the platform logs: Python block-buffers stdout when it is not a tty, so the
# boot lines this deployment relies on for observability ([auth] state, the
# interactive-gate summary, [satellite-traffic] wiring) can sit invisible
# while logging-based lines sail through on stderr. Those boot lines ARE the
# deploy acceptance check here — three absences and one presence — so they
# cannot be the ones that go missing.
ENV PYTHONUNBUFFERED=1

# curl only — the HEALTHCHECK below uses it. Deliberately NO nodejs/npm.
# The template's fork lineage carried an apt-installed Node toolchain that
# `npm install`ed a package.json nothing in the repo used, shipping a
# vulnerable transitive dependency into every production image (issue #12,
# CVE-2026-1615); it was dropped at the template in 1.6.9. This repo never
# had it: the 1.0.0 rebuild removed webpack, babel and package.json outright,
# and the JS that ships — the hand-authored shim and Google's vendored UMD
# bundle — is COMMITTED, not built. A docs site is a Python app. If this
# package ever does build its component's JS, that toolchain gets added
# knowingly, not inherited.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Update pip
RUN pip install --upgrade pip

# Install core dependencies explicitly (helps with dependency resolution)
RUN pip install pandas>=1.2.3 plotly>=5.0.0 pydantic>=2.3.0

# vendor/ holds the dash_clerk_auth sdist, which requirements.txt references by
# relative path (./vendor/dash_clerk_auth-1.0.5.tar.gz) — so it must be present
# BEFORE the install, not arrive with the later `COPY . .`. It is not on PyPI:
# the dist/ tarball is the release, admitted only by its recorded sha256.
#
# (The vendored model-viewer bundle is a different thing entirely — it lives
# inside the dash_model_viewer package as package data.)
# CACHE SEMANTICS (the round-2 fleet lesson, found by pannellum 2026-08-22):
# this layer re-runs ONLY when vendor/ or requirements.txt bytes change. A
# `>=` floor can NEVER pull a newer release through a cache hit — a code-only
# commit rebuilds the app layers below while pip silently keeps whatever
# version the image was first built with. Ship every dependency upgrade as a
# floor bump in requirements.txt (grep the number — it also lives in run.py's
# boot floor and the tests): the bump IS the cache bust, and the boot floor
# turns a stale image from a silent downgrade into a loud refusal to start.
COPY vendor/ ./vendor/
COPY requirements.txt .
RUN pip install -r requirements.txt
# markdown2dash pins gunicorn<22, conflicting with the CVE-driven gunicorn>=23
# in requirements.txt (CVE-2024-6827, CVE-2024-1135 — request smuggling). Its
# real dependencies are all in requirements.txt already, so it is installed
# alone, without letting pip see the spurious pin. CI asserts the resulting
# gunicorn version inside this image, which is what keeps the dodge honest.
RUN pip install --no-deps markdown2dash==0.1.2

COPY . .

# The site documents the package in THIS checkout, not whatever is on PyPI.
RUN pip install --no-deps .

# The 2plot.ai hub's hourly sweep probes /healthz; give the container the same
# check so an unhealthy process is visible to the orchestrator too.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:${PORT:-8550}/healthz || exit 1

EXPOSE 8550
# Shell form on purpose: exec-form CMD never expands env, so the old
# ["gunicorn", ..., "0.0.0.0:8550"] hardcoded the port whatever the platform
# asked for. run.py has honored $PORT since 1.6.8; this lane did not, and
# only worked on Render because Render port-detects. The default lives at the
# POINT OF USE (${PORT:-8550}, in both the bind and the probe above) — an
# ENV PORT=8550 default would look equivalent and is not: a platform that
# sets PORT empty collapses a bare ${PORT} to `0.0.0.0:` and the bind fails.
CMD gunicorn run:server -b 0.0.0.0:${PORT:-8550}
