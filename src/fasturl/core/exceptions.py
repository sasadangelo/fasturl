# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Domain / application exceptions and global FastAPI exception handlers.

All domain exceptions are pure Python — zero FastAPI imports — so they can be
raised from services without coupling the domain to the HTTP layer.

The ``register_exception_handlers`` function wires these exceptions to the
standardised error envelope defined in ``docs/api-design.md``:

    {
        "success": false,
        "error": "SHORT_ERROR_CODE",
        "details": ["field_name -> explanation"]
    }
"""

from __future__ import annotations

import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger

# ---------------------------------------------------------------------------
# Domain exceptions — HTTP-agnostic; raised from services/
# ---------------------------------------------------------------------------


class AppError(Exception):
    """Base application / domain exception.

    Args:
        message: Short error code string (e.g. ``"LINK_NOT_FOUND"``).
        status_code: HTTP status code to return to the caller.
        details: List of human-readable field-level explanations.
    """

    def __init__(self, message: str, status_code: int = 400, details: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details: list[str] = details or []


class LinkNotFoundError(AppError):
    """Raised when no link exists for a given code."""

    def __init__(self, code: str) -> None:
        super().__init__(
            message="LINK_NOT_FOUND",
            status_code=404,
            details=[f"code -> No link found with code '{code}'"],
        )


class AliasAlreadyTakenError(AppError):
    """Raised when a requested custom alias is already in use."""

    def __init__(self, alias: str) -> None:
        super().__init__(
            message="ALIAS_ALREADY_TAKEN",
            status_code=409,
            details=[f"custom_code -> The alias '{alias}' is already in use"],
        )


class LinkExpiredError(AppError):
    """Raised when a visitor tries to use a link that has passed its expiry date."""

    def __init__(self, code: str, expired_at: str) -> None:
        super().__init__(
            message="LINK_EXPIRED",
            status_code=410,
            details=[f"code -> Link '{code}' expired on {expired_at}"],
        )


class ValidationError(AppError):
    """Raised for business-rule validation failures not caught by Pydantic."""

    def __init__(self, details: list[str]) -> None:
        super().__init__(
            message="VALIDATION_ERROR",
            status_code=400,
            details=details,
        )


# ---------------------------------------------------------------------------
# Global FastAPI exception handlers
# ---------------------------------------------------------------------------


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all global exception handlers to the FastAPI application.

    Args:
        app: The FastAPI application instance.
    """

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Handle Pydantic request validation failures (400)."""
        error_details: list[str] = []
        for e in exc.errors():
            loc = " -> ".join(str(x) for x in e["loc"])
            msg = e["msg"]
            error_details.append(f"{loc}: {msg}")

        logger.bind(name="exceptions").warning(f"Invalid request payload at {request.url}: {error_details}")

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "VALIDATION_ERROR",
                "details": error_details,
            },
        )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """Handle domain / application exceptions."""
        logger.bind(name="exceptions").warning(f"Application error at {request.url}: {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle any unhandled exception with a generic 500 response."""
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        logger.bind(name="exceptions").error(f"Unhandled exception at {request.url}:\n{tb}")

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "INTERNAL_SERVER_ERROR",
                "details": ["An unexpected error occurred. Please contact support."],
            },
        )
