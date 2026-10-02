# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Async SQLAlchemy repository for the ``Link`` aggregate.

This layer is strictly data-access only — no business rules, no status
calculations, no pricing logic. It answers only: "How do I store or retrieve
a Link record?"
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.engine.result import Result
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Select

from fasturl.models.link import Link


class LinkRepository:
    """Data-access layer for the ``links`` table.

    Args:
        session: An injected async SQLAlchemy session for the current request.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_code(self, code: str) -> Link | None:
        """Return the ``Link`` with the given code, or ``None`` if not found.

        Args:
            code: The Base62 short code or custom alias.

        Returns:
            The matching ``Link`` ORM instance, or ``None``.
        """
        result: Result[Link] = await self._session.execute(select(Link).where(Link.code == code))
        return result.scalar_one_or_none()

    async def list_links(
        self,
        status: str | None = None,
        is_active: bool | None = True,
        sort_field: str = "created_at",
        sort_desc: bool = True,
    ) -> list[Link]:
        """Return all links with optional filtering and sorting.

        Args:
            status: Filter by inspection_status (``pending_analysis``, ``active``, ``unreachable``).
            is_active: Filter by is_active flag. ``None`` returns all.
            sort_field: Column to sort by (``created_at`` or ``clicks_count``).
            sort_desc: Sort direction; ``True`` = descending.

        Returns:
            List of ``Link`` ORM instances matching the filters.
        """
        stmt: Select[Link] = select(Link)

        if status is not None:
            stmt = stmt.where(Link.inspection_status == status)
        if is_active is not None:
            stmt = stmt.where(Link.is_active == is_active)

        # Allowed sort columns — guard against SQL injection via explicit allowlist
        _sort_column_map = {
            "created_at": Link.created_at,
            "clicks_count": Link.clicks_count,
        }
        col = _sort_column_map.get(sort_field, Link.created_at)
        stmt = stmt.order_by(col.desc() if sort_desc else col.asc())

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, link: Link) -> Link:
        """Persist a new ``Link`` record and return the refreshed instance.

        Args:
            link: A fully-constructed (but not yet persisted) ``Link`` instance.

        Returns:
            The ``Link`` instance after the INSERT, with server-generated values populated.
        """
        self._session.add(instance=link)
        await self._session.commit()
        await self._session.refresh(instance=link)
        return link

    async def soft_delete(self, code: str) -> bool:
        """Set ``is_active = False`` for the link with the given code.

        Args:
            code: The Base62 short code or custom alias.

        Returns:
            ``True`` if a row was updated, ``False`` if no matching link was found.
        """
        result: Result[int] = await self._session.execute(
            update(table=Link)
            .where(Link.code == code)
            .values(is_active=False, updated_at=datetime.now(UTC).replace(tzinfo=None))
            .returning(Link.id)
        )
        await self._session.commit()
        return result.scalar_one_or_none() is not None

    async def reset_inspection(self, code: str) -> bool:
        """Reset the inspection snapshot to ``pending_analysis`` for the given link.

        Args:
            code: The Base62 short code or custom alias.

        Returns:
            ``True`` if a row was updated, ``False`` if no matching link was found.
        """
        result: Result[int] = await self._session.execute(
            update(table=Link)
            .where(Link.code == code)
            .values(
                inspection_status="pending_analysis",
                http_status_code=None,
                latency_ms=None,
                title=None,
                description=None,
                image_url=None,
                last_checked_at=None,
                updated_at=datetime.now(UTC).replace(tzinfo=None),
            )
            .returning(Link.id)
        )
        await self._session.commit()
        return result.scalar_one_or_none() is not None

    async def update_inspection(
        self,
        code: str,
        *,
        status: str,
        http_status_code: int | None,
        latency_ms: float | None,
        title: str | None,
        description: str | None,
        image_url: str | None,
    ) -> None:
        """Persist the result of a completed inspection task.

        Args:
            code: The Base62 short code or custom alias.
            status: New inspection status (``active`` or ``unreachable``).
            http_status_code: HTTP response code received from the target URL.
            latency_ms: Round-trip latency in milliseconds.
            title: HTML ``<title>`` extracted from the target page.
            description: OpenGraph or meta description.
            image_url: OpenGraph image URL.
        """
        await self._session.execute(
            update(Link)
            .where(Link.code == code)
            .values(
                inspection_status=status,
                http_status_code=http_status_code,
                latency_ms=latency_ms,
                title=title,
                description=description,
                image_url=image_url,
                last_checked_at=datetime.now(UTC).replace(tzinfo=None),
                updated_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        await self._session.commit()

    async def increment_clicks(self, code: str) -> None:
        """Atomically increment ``clicks_count`` and update ``last_clicked_at``.

        Args:
            code: The Base62 short code or custom alias.
        """
        from sqlalchemy import func  # local import to avoid top-level circular deps

        await self._session.execute(
            update(Link)
            .where(Link.code == code)
            .values(
                clicks_count=Link.clicks_count + 1,
                last_clicked_at=func.now(),
                updated_at=func.now(),
            )
        )
        await self._session.commit()

    async def code_exists(self, code: str) -> bool:
        """Return ``True`` if any link (active or inactive) uses the given code.

        Args:
            code: The Base62 code to check.

        Returns:
            ``True`` if the code is already taken, ``False`` otherwise.
        """
        result: Result[int] = await self._session.execute(select(Link.id).where(Link.code == code))
        return result.scalar_one_or_none() is not None
