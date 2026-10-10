# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Pydantic v2 request and response DTOs for the Links API.

Request schemas validate and constrain inbound data.
Response schemas define the exact contract returned to clients — the
``response_model`` parameter on each route handler filters ORM data through
these shapes, preventing internal fields from leaking.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from re import Pattern
from typing import Annotated, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

# ---------------------------------------------------------------------------
# Reusable annotated path parameter type (imported by routers)
# ---------------------------------------------------------------------------

ShortCodePath: TypeAlias = Annotated[
    str,
    Field(
        min_length=7,
        max_length=16,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="The unique short code identifier of the link",
        examples=["aB3x9zK", "mybrand"],
    ),
]

_BASE62_PATTERN: Pattern[str] = re.compile(r"^[a-zA-Z0-9]{7,16}$")

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class LinkCreateRequest(BaseModel):
    """Request body for ``POST /api/v1/links``.

    Attributes:
        target_url: Destination URL (HTTP/HTTPS only).
        custom_code: Optional custom alias (Base62, 7–16 chars).
        expires_at: Optional expiration timestamp (must be in the future).
    """

    target_url: HttpUrl = Field(
        description="Destination URL to shorten. Must be HTTP or HTTPS.",
        examples=["https://example.com/very/long/article/path"],
    )
    custom_code: str | None = Field(
        default=None,
        min_length=7,
        max_length=16,
        description="Optional custom alias (Base62 [a-zA-Z0-9], 7–16 chars).",
        examples=["mybrand"],
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Optional expiration datetime in ISO 8601 format. Must be in the future.",
        examples=["2026-01-01T00:00:00Z"],
    )

    @field_validator("custom_code")
    @classmethod
    def validate_custom_code(cls, v: str | None) -> str | None:
        """Ensure the custom code uses the Base62 alphabet only."""
        if v is not None and not _BASE62_PATTERN.match(v):
            raise ValueError("custom_code must contain only alphanumeric characters [a-zA-Z0-9]")
        return v

    @field_validator("expires_at")
    @classmethod
    def normalize_expires_at_to_utc(cls, v: datetime | None) -> datetime | None:
        """Convert timezone-aware datetimes to naive UTC, the convention used by all DB timestamps.

        Naive input is assumed to be UTC already. Without this, an offset such as ``+02:00``
        would be dropped instead of converted, and PostgreSQL rejects aware datetimes for
        ``TIMESTAMP WITHOUT TIME ZONE`` columns.
        """
        if v is not None and v.tzinfo is not None:
            return v.astimezone(UTC).replace(tzinfo=None)
        return v

    @model_validator(mode="after")
    def validate_expires_at_future(self) -> LinkCreateRequest:
        """Reject expiration dates that are not in the future."""
        if self.expires_at is not None and self.expires_at <= datetime.now(UTC).replace(tzinfo=None):
            raise ValueError("expires_at -> Expiration date must be in the future")
        return self


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class InspectionResponse(BaseModel):
    """Embedded inspection snapshot inside ``LinkResponse``.

    Attributes:
        status: Current inspection status (``pending_analysis``, ``active``, ``unreachable``).
        http_status_code: HTTP response code from the target URL check.
        latency_ms: Round-trip latency in milliseconds.
        title: HTML ``<title>`` of the target page.
        description: OpenGraph or meta description.
        image_url: OpenGraph image URL.
        last_checked_at: Timestamp of the last inspection execution.
    """

    model_config = ConfigDict(from_attributes=True)

    status: str
    http_status_code: int | None = None
    latency_ms: float | None = None
    title: str | None = None
    description: str | None = None
    image_url: str | None = None
    last_checked_at: datetime | None = None


class MetricsResponse(BaseModel):
    """Embedded click metrics snapshot inside ``LinkResponse``.

    Attributes:
        clicks_count: Total number of successful redirects.
        last_clicked_at: Timestamp of the most recent redirect.
    """

    model_config = ConfigDict(from_attributes=True)

    clicks_count: int
    last_clicked_at: datetime | None = None


class LinkResponse(BaseModel):
    """Full link representation returned by the management API.

    Internal fields (``id``) are excluded — only ``code`` is exposed as the
    public identifier, matching the API contract in ``docs/api-design.md``.

    Attributes:
        code: The short code / custom alias.
        short_url: The fully-qualified short URL.
        target_url: The destination URL.
        is_active: Whether the link is active (not soft-deleted).
        expires_at: Optional expiration datetime.
        inspection: Current inspection snapshot.
        metrics: Current click metrics.
        created_at: Creation timestamp.
        updated_at: Last-modification timestamp.
    """

    model_config = ConfigDict(from_attributes=False)

    code: str
    short_url: str
    target_url: str
    is_active: bool
    expires_at: datetime | None = None
    inspection: InspectionResponse
    metrics: MetricsResponse
    created_at: datetime
    updated_at: datetime
