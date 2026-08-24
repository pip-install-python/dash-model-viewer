"""
FastAPI showcase routes for the documentation boilerplate.

The AI/LLM surfaces (``/llms.txt``, ``/<page>/llms.txt``, ``/robots.txt``,
``/sitemap.xml``) are mounted by ``dash-improve-my-llms`` 2.0 directly —
the package detects the FastAPI backend and registers its own router.
This module only carries the **showcase** surfaces that demonstrate
first-class OpenAPI integration under Dash 4.1+'s FastAPI backend:

- ``/healthz``       — liveness probe
- ``/api/backend``   — active backend info
- ``/api/pages``     — registered Dash pages, sortable list

These show up in Swagger UI at ``/docs`` and ReDoc at ``/redoc`` because
each route declares a Pydantic ``response_model``.
"""
from __future__ import annotations

from typing import List, Optional

import dash
from fastapi import APIRouter, FastAPI, Request
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic models — these power the OpenAPI schema at /docs
# ---------------------------------------------------------------------------


class BackendInfoModel(BaseModel):
    name: str = Field(..., description="Active backend identifier")
    label: str = Field(..., description="Human-readable backend label")
    is_async: bool = Field(..., description="True for ASGI backends (fastapi, quart)")
    description: str


class PageSummary(BaseModel):
    name: str
    path: str
    title: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None


class PageListResponse(BaseModel):
    backend: str
    count: int
    pages: List[PageSummary]


class HealthResponse(BaseModel):
    """The probe contract, identical on every backend.

    ``lib.health.health_payload`` is the single source — this model only
    types it for Swagger. It used to be built independently here, which
    meant a FastAPI deployment silently lacked ``build``: cd.yml's
    build-match wait polls /healthz for exactly that field, so it would
    have fallen into the "predates the build field" warning path forever,
    verifying whichever release happened to be serving — the muicharts
    defect the wait was written to prevent, reintroduced per-backend
    (found on llms-2plot-dev, 2026-08-23).
    """

    ok: bool = True
    backend: str
    dash_version: str
    # Optional because they are environment-dependent, not backend-dependent.
    build: Optional[str] = None
    app: Optional[str] = None
    geo: Optional[dict] = None


# ---------------------------------------------------------------------------
# Router factories
# ---------------------------------------------------------------------------


def build_api_router(app, backend_info) -> APIRouter:
    """Native FastAPI showcase routes — populate /docs and /redoc."""
    router = APIRouter(prefix="/api", tags=["showcase"])

    @router.get("/backend", response_model=BackendInfoModel, summary="Active backend")
    def get_backend() -> BackendInfoModel:
        return BackendInfoModel(
            name=backend_info.name,
            label=backend_info.label,
            is_async=backend_info.is_async,
            description=backend_info.description,
        )

    @router.get(
        "/pages",
        response_model=PageListResponse,
        summary="Registered Dash pages",
    )
    def list_pages() -> PageListResponse:
        pages: List[PageSummary] = []
        for p in dash.page_registry.values():
            pages.append(PageSummary(
                name=p.get("name"),
                path=p.get("path"),
                title=p.get("title"),
                description=p.get("description"),
                icon=p.get("icon"),
            ))
        return PageListResponse(
            backend=backend_info.name,
            count=len(pages),
            pages=sorted(pages, key=lambda x: x.path),
        )

    return router


def build_health_router() -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/healthz", response_model=HealthResponse, summary="Liveness probe")
    def healthz(request: Request) -> HealthResponse:
        # One payload builder for all three backends — see HealthResponse.
        # Built per request: `geo` reports live state, and this route is
        # mounted long before any geo configuration runs. The request's
        # headers go with it — geo's `resolved` reads the country header
        # from THIS request, and the Flask-context fallback inside
        # health_payload can never see a Starlette request (pannellum's
        # production healthz answered "no request context" until this).
        from lib.health import health_payload

        return HealthResponse(**health_payload("fastapi", headers=request.headers))

    return router


def register_asgi_routes(app, backend_info) -> None:
    """Mount the showcase FastAPI routers on ``app.server``.

    These must be registered **before** ``add_llms_routes(app)`` so that
    the package's catch-all ``/<page>/llms.txt`` matcher does not shadow
    ``/healthz`` or ``/api/*``.
    """
    server: FastAPI = app.server  # type: ignore[assignment]
    server.include_router(build_health_router())
    server.include_router(build_api_router(app, backend_info))
