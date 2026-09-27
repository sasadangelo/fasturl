# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""FastAPI application entry point.

Initialises settings, logging, database engine, shared HTTP client, and the
FastAPI application with its lifespan context. Registers global exception
handlers, production middlewares, and all routers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from fasturl.api.middleware import AuditLoggingMiddleware, CorrelationIdMiddleware, TimingMiddleware
from fasturl.api.routers import links, redirect
from fasturl.core.config import settings
from fasturl.core.database import close_db, init_db
from fasturl.core.exceptions import register_exception_handlers
from fasturl.core.log import setup_logging

_log = logger.bind(name="main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — startup and graceful shutdown."""
    # --- Startup ---
    setup_logging(
        level=settings.log.level,
        console=settings.log.console,
        file=settings.log.file,
        rotation=settings.log.rotation,
        retention=settings.log.retention,
        compression=settings.log.compression,
    )
    _log.info(f"Starting FastURL v{app.version}...")

    # 1. Initialise async DB engine and bounded connection pool
    await init_db()

    # 2. Create shared async HTTP client for background URL inspection
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.inspector.timeout_seconds),
        follow_redirects=True,
        max_redirects=settings.inspector.max_redirects,
        headers={"User-Agent": "FastURL-Inspector/0.1"},
    )

    _log.info("Application startup complete. Ready to receive requests.")
    yield

    # --- Shutdown ---
    _log.info("Initiating graceful shutdown...")

    if hasattr(app.state, "http_client") and app.state.http_client is not None:
        await app.state.http_client.aclose()
        _log.info("Shared HTTP client closed.")

    await close_db()
    _log.info("Application shutdown complete.")


# ---------------------------------------------------------------------------
# OpenAPI tag metadata
# ---------------------------------------------------------------------------

tags_metadata: list[dict[str, str]] = [
    {
        "name": "Links",
        "description": "Create, list, retrieve, and delete shortened links.",
    },
    {
        "name": "Inspection",
        "description": "Manually trigger a background URL re-inspection.",
    },
    {
        "name": "Redirect",
        "description": "Public short-URL redirect endpoint.",
    },
]

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app: FastAPI = FastAPI(
    title="FastURL",
    description="High-performance URL shortening and link inspection API.",
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=tags_metadata,
)

# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------

register_exception_handlers(app)

# ---------------------------------------------------------------------------
# Middlewares (outermost registered last — Starlette applies in reverse order)
# ---------------------------------------------------------------------------

app.add_middleware(
    middleware_class=CORSMiddleware,
    allow_origins=["*"],  # Tighten to explicit origins in production
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(middleware_class=AuditLoggingMiddleware)
app.add_middleware(middleware_class=TimingMiddleware)
app.add_middleware(middleware_class=CorrelationIdMiddleware)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(router=links.router)
# Redirect router is mounted last at root "/" to avoid shadowing /api/v1/* routes
app.include_router(router=redirect.router)
