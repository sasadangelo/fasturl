# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""SQLAlchemy ORM model for the ``links`` table.

The ``LinkDAO`` model represents the single Aggregate Root of the FastURL domain.
It is a data-access object (DAO) — only the repository and service layers are
permitted to import it. External layers (routers) interact with it only through
the repository facade or response DTOs.

All Value Objects (ShortCode, TargetUrl, LinkMetrics, LinkInspection) are
stored as flat columns, following the single-table design in ``sql/schema.sql``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


INSPECTION_STATUSES: tuple[str, ...] = ("pending_analysis", "active", "unreachable")
"""Allowed values of ``links.inspection_status``.

Mapped to a native ``ENUM`` type on PostgreSQL and to ``VARCHAR`` + ``CHECK`` constraint on SQLite.
"""


class LinkDAO(Base):
    """ORM representation of the ``links`` table.

    Attributes:
        id: Internal surrogate PK — never exposed via API.
        code: Base62 ShortCode (7-16 chars) — sole public identifier.
        target_url: Validated destination URL (HTTP/HTTPS).
        is_active: Soft-delete flag; False means the link is disabled.
        expires_at: Optional expiration datetime; NULL means never expires.
        inspection_status: Current health status of the target URL.
        http_status_code: HTTP response code from the last inspection.
        latency_ms: Round-trip latency in milliseconds from the last inspection.
        title: HTML <title> from the target page.
        description: og:description or meta description from the target page.
        image_url: og:image URL from the target page.
        last_checked_at: Timestamp of the last inspection execution.
        clicks_count: Total successful redirects.
        last_clicked_at: Timestamp of the most recent redirect.
        created_at: Record creation timestamp.
        updated_at: Record last-modification timestamp.
    """

    __tablename__ = "links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(length=16), nullable=False, unique=True, index=True)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    # LinkInspection VO — embedded columns
    inspection_status: Mapped[str] = mapped_column(
        Enum(*INSPECTION_STATUSES, name="inspection_status", create_constraint=True),
        nullable=False,
        default="pending_analysis",
    )
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    title: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    # LinkMetrics VO — embedded columns
    clicks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_clicked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
    )
