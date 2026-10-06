# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""HTTP router for the ``/api/v1/links`` resource.

Handlers are thin by design — they parse HTTP inputs, invoke the service layer
via ``Depends``, pass the request-scoped ``BackgroundTasks`` as a scheduler,
assign status codes, and return filtered DTOs. Zero business logic lives here.
"""

from __future__ import annotations

from typing import Annotated, TypeAlias

from fastapi import APIRouter, BackgroundTasks, Path, Query, status
from fastapi.responses import Response

from fasturl.api.dependencies import LinkServiceDep
from fasturl.api.schemas.link_schemas import LinkCreateRequest, LinkResponse
from fasturl.core.exceptions import ValidationError

router: APIRouter = APIRouter(
    prefix="/api/v1/links",
    tags=["Links"],
)

# ---------------------------------------------------------------------------
# Reusable annotated path parameter
# ---------------------------------------------------------------------------

_CodePath: TypeAlias = Annotated[
    str,
    Path(
        min_length=7,
        max_length=16,
        description="Base62 short code or custom alias identifying the link",
        examples=["aB3x9zK", "mybrand"],
    ),
]

# ---------------------------------------------------------------------------
# Allowed status values for the ?status= query parameter
# ---------------------------------------------------------------------------

_VALID_STATUSES = {"pending_analysis", "active", "unreachable"}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    path="",
    response_model=LinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new shortened link",
    description=(
        "Creates a new Link aggregate. If ``custom_code`` is omitted, a random 7-character "
        "Base62 code is generated. A background inspection task is automatically dispatched "
        "to check target URL health and extract OpenGraph metadata. Responds immediately "
        "with 201 Created without waiting for inspection to complete."
    ),
)
async def create_link(
    body: LinkCreateRequest,
    service: LinkServiceDep,
    background_tasks: BackgroundTasks,
) -> LinkResponse:
    """Create a new shortened link and dispatch a background inspection."""
    return await service.create_link(
        target_url=str(body.target_url),
        custom_code=body.custom_code,
        expires_at=body.expires_at,
        scheduler=background_tasks,
    )


@router.get(
    path="",
    response_model=list[LinkResponse],
    status_code=status.HTTP_200_OK,
    summary="List all shortened links with optional filtering",
    description=(
        "Returns a flat array of all links. Supports filtering by inspection status "
        "and operational state. No pagination — the dataset is intentionally small "
        "(demo scope)."
    ),
)
async def list_links(
    service: LinkServiceDep,
    status_filter: Annotated[
        str | None,
        Query(
            alias="status",
            description="Filter by inspection status",
            examples=["active"],
        ),
    ] = None,
    is_active: Annotated[
        bool | None,
        Query(description="Filter by operational state. Omit to return all."),
    ] = True,
    sort: Annotated[
        str,
        Query(
            description=(
                "Comma-separated sort fields. Prefix ``-`` for descending. Allowed: ``created_at``, ``clicks_count``."
            ),
            examples=["-created_at"],
        ),
    ] = "-created_at",
) -> list[LinkResponse]:
    """List links with optional filtering and sorting."""
    if status_filter is not None and status_filter not in _VALID_STATUSES:
        raise ValidationError([f"status -> Must be one of: {', '.join(sorted(_VALID_STATUSES))}"])

    return await service.list_links(
        status=status_filter,
        is_active=is_active,
        sort=sort,
    )


@router.get(
    path="/{code}",
    response_model=LinkResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve full details of a single link",
    description=(
        "Returns the complete Link aggregate including inspection snapshot and click metrics. "
        "Returns 404 if the code does not exist (regardless of is_active state)."
    ),
)
async def get_link(
    code: _CodePath,
    service: LinkServiceDep,
) -> LinkResponse:
    """Get a single link by its short code."""
    return await service.get_link(code)


@router.delete(
    path="/{code}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Soft-delete (disable) a link",
    description=(
        "Sets ``is_active = false`` on the link. The record is retained for audit purposes. "
        "After deletion, ``GET /{code}`` returns 404 for visitors."
    ),
)
async def delete_link(
    code: _CodePath,
    service: LinkServiceDep,
) -> None:
    """Soft-delete a link by its short code."""
    await service.delete_link(code)


@router.post(
    path="/{code}/inspect",
    response_model=LinkResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Links", "Inspection"],
    summary="Manually trigger a background re-inspection of a link's target URL",
    description=(
        "Resets ``inspection_status`` to ``pending_analysis`` and dispatches a new background "
        "inspection task. Responds immediately with 202 Accepted and the current link snapshot. "
        "Accepts re-trigger even if the link is already in ``pending_analysis`` state (idempotent)."
    ),
)
async def trigger_inspection(
    code: _CodePath,
    service: LinkServiceDep,
    background_tasks: BackgroundTasks,
) -> LinkResponse:
    """Reset inspection state and dispatch a new background inspection task."""
    return await service.trigger_reinspection(code, scheduler=background_tasks)
