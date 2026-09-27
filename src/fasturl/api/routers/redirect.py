# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""HTTP router for the public redirect endpoint ``GET /{code}``.

This router is mounted at the root path (no ``/api/v1/`` prefix) because the
short URL must remain stable and as short as possible (consumer-facing URL).

On successful resolution the handler issues a ``307 Temporary Redirect`` to
preserve accurate click tracking (307 is not cached by browsers, unlike 301).
Click metrics are incremented atomically via a background task after the
redirect response is sent — the visitor is not blocked by the DB write.
"""

from __future__ import annotations

from typing import Annotated, TypeAlias

from fastapi import APIRouter, BackgroundTasks, Path
from fastapi.responses import RedirectResponse

from fasturl.api.dependencies import LinkServiceDep

router: APIRouter = APIRouter(tags=["Redirect"])

_CodePath: TypeAlias = Annotated[
    str,
    Path(
        min_length=1,
        description="Base62 short code or custom alias to resolve",
        examples=["aB3x9zK", "mybrand"],
    ),
]


@router.get(
    path="/{code}",
    status_code=307,
    response_class=RedirectResponse,
    summary="Resolve and redirect a short URL to its target destination",
    description=(
        "Public endpoint mounted at the root path. Resolves ``code`` to its ``target_url`` "
        "and issues an HTTP ``307 Temporary Redirect``. "
        "Uses 307 (not 301) to prevent browser caching and preserve accurate click tracking. "
        "Returns ``410 Gone`` for expired links and ``404 Not Found`` for inactive or non-existent codes."
    ),
)
async def redirect_short_url(
    code: _CodePath,
    service: LinkServiceDep,
    background_tasks: BackgroundTasks,
) -> RedirectResponse:
    """Resolve the short code and issue a 307 redirect; increment clicks in background."""
    target_url: str = await service.resolve_for_redirect(code)

    background_tasks.add_task(
        func=service._repository.increment_clicks,
        code=code,
    )

    return RedirectResponse(url=target_url, status_code=307)
