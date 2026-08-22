# 3.12 to match render.yaml's PYTHON_VERSION. The boilerplate's Dockerfile
# builds on 3.11.8 while its render.yaml deploys 3.12.0, so its container
# battery green-lights a Python that production never runs. Same base here as
# the service, or the gate is testing something else.
FROM python:3.12-slim

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
COPY requirements.txt .
COPY vendor/ ./vendor/
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
    CMD curl -fsS http://localhost:8550/healthz || exit 1

EXPOSE 8550
CMD ["gunicorn", "run:server", "-b", "0.0.0.0:8550"]
