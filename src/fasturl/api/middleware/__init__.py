# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Production middlewares for FastURL.

Middlewares are registered in ``main.py`` via ``app.middleware("http")``.

Included:
- **Correlation ID** — Generates or propagates ``X-Request-ID`` for distributed tracing.
- **Process Timing** — Adds ``X-Process-Time`` response header (milliseconds).
- **Structured Audit Logging** — Logs method, path, status, and duration on completion.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

_log = logger.bind(name="Middleware")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Propagate or generate a ``X-Request-ID`` header for distributed tracing.

    If the incoming request already carries an ``X-Request-ID`` header the
    value is forwarded; otherwise a new UUID4 is generated.  The ID is
    attached to the response header so clients can correlate log entries.

    Args:
        app: The ASGI application to wrap.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Inject or forward the correlation ID header.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The response with ``X-Request-ID`` header attached.
        """
        request_id: str = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Add ``X-Process-Time`` response header with request duration in milliseconds.

    Args:
        app: The ASGI application to wrap.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Measure handler duration and attach it to the response.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The response with ``X-Process-Time`` header attached.
        """
        start: float = time.monotonic()
        response: Response = await call_next(request)
        duration_ms: float = round(number=(time.monotonic() - start) * 1000, ndigits=2)
        response.headers["X-Process-Time"] = f"{duration_ms}ms"
        return response


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Log a structured audit record for every completed HTTP request.

    Format: ``METHOD /path → status_code  duration_ms``

    Args:
        app: The ASGI application to wrap.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Log method, path, status, and duration after each request.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The response unchanged.
        """
        start: float = time.monotonic()
        response: Response = await call_next(request)
        duration_ms: float = round(number=(time.monotonic() - start) * 1000, ndigits=2)
        request_id: Any | str = getattr(request.state, "request_id", "-")
        _log.info(
            f"{request.method} {request.url.path} → {response.status_code}  {duration_ms}ms  [request_id={request_id}]"
        )
        return response
