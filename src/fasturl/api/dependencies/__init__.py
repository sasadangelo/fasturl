# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""FastAPI dependency providers.

Defines all ``Depends``-injectable factories for database sessions,
shared HTTP clients, repositories, and services. Consumers import the
typed ``Annotated`` aliases (e.g. ``LinkServiceDep``) and declare them as
function parameters — FastAPI resolves the dependency graph automatically.

Usage example::

    from fasturl.api.dependencies import LinkServiceDep

    @router.get("/links/{code}")
    async def get_link(code: str, service: LinkServiceDep) -> LinkResponse:
        return await service.get_link(code)
"""

from __future__ import annotations

from typing import Annotated, TypeAlias

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from fasturl.core.database import get_db
from fasturl.repositories.link_repository import LinkRepository
from fasturl.services.link_service import LinkService

# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------

DBSessionDep: TypeAlias = Annotated[AsyncSession, Depends(dependency=get_db)]


# ---------------------------------------------------------------------------
# Shared async HTTP client (sourced from lifespan app.state)
# ---------------------------------------------------------------------------


def _get_http_client(request: Request) -> httpx.AsyncClient:
    """Return the shared ``httpx.AsyncClient`` stored in ``app.state``.

    Args:
        request: The current FastAPI ``Request`` object.

    Returns:
        The shared async HTTP client.
    """
    return request.app.state.http_client


HTTPClientDep: TypeAlias = Annotated[httpx.AsyncClient, Depends(dependency=_get_http_client)]


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


def _get_link_repository(session: DBSessionDep) -> LinkRepository:
    """Construct a ``LinkRepository`` scoped to the current DB session.

    Args:
        session: Injected async database session.

    Returns:
        A ``LinkRepository`` instance bound to the session.
    """
    return LinkRepository(session)


LinkRepoDep: TypeAlias = Annotated[LinkRepository, Depends(dependency=_get_link_repository)]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


def _get_link_service(repository: LinkRepoDep) -> LinkService:
    """Construct the ``LinkService`` with its injected repository.

    Args:
        repository: Injected ``LinkRepository``.

    Returns:
        A ``LinkService`` instance.
    """
    return LinkService(repository=repository)


LinkServiceDep: TypeAlias = Annotated[LinkService, Depends(dependency=_get_link_service)]
