# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""FastAPI application entry point.

Initialises settings, logging, database engine, and the FastAPI app with its
lifespan context. All routers are registered here.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fasturl.core.config import settings
from fasturl.core.database import close_db, init_db
from fasturl.core.log import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — startup and shutdown hooks."""
    # Startup
    setup_logging(
        level=settings.log.level,
        console=settings.log.console,
        file=settings.log.file,
        rotation=settings.log.rotation,
        retention=settings.log.retention,
        compression=settings.log.compression,
    )
    await init_db()

    yield

    # Shutdown
    await close_db()


app = FastAPI(
    title="FastURL",
    description="High-performance URL shortening and link inspection API.",
    version="0.1.0",
    lifespan=lifespan,
)

# Register routers here once implemented:
# from fasturl.api.routers import links, redirect
# app.include_router(links.router, prefix="/api/v1/links", tags=["links"])
# app.include_router(redirect.router, tags=["redirect"])
