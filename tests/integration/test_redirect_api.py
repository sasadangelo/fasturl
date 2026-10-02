# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Integration tests for the public redirect endpoint GET /{code}.

Boundary: FastAPI ASGI transport → redirect router → link service →
repository → in-memory SQLite.

Covers JS-006:
  - Active link → 307 Temporary Redirect with correct Location header
  - Click count incremented after successful redirect
  - Expired link → 410 Gone
  - Inactive (soft-deleted) link → 404 Not Found
  - Non-existent code → 404 Not Found
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from httpx._models import Response
from sqlalchemy.ext.asyncio import AsyncSession

from fasturl.models.link import Link
from fasturl.repositories.link_repository import LinkRepository

# ---------------------------------------------------------------------------
# Helper — seed a Link directly into the test DB
# ---------------------------------------------------------------------------


async def _seed_link(
    db_session: AsyncSession,
    *,
    code: str,
    target_url: str = "https://example.com",
    is_active: bool = True,
    expires_at: datetime | None = None,
) -> Link:
    """Insert a Link record directly into the test database."""
    now: datetime = datetime.now(UTC).replace(tzinfo=None)
    link: Link = Link(
        code=code,
        target_url=target_url,
        is_active=is_active,
        expires_at=expires_at,
        inspection_status="active",
        clicks_count=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add(instance=link)
    await db_session.commit()
    await db_session.refresh(instance=link)
    return link


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRedirectEndpoint:
    """JS-006 — public short-URL redirect."""

    async def test_active_link_returns_307(
        self,
        api_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """A GET on an active, non-expired code returns 307 with a Location header."""
        await _seed_link(db_session, code="redir01", target_url="https://example.com/dest")

        response: Response = await api_client.get(url="/redir01", follow_redirects=False)

        assert response.status_code == 307
        assert response.headers["location"] == "https://example.com/dest"

    async def test_click_count_incremented_after_redirect(
        self,
        api_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """After a successful redirect the click count in the DB is incremented by 1."""
        await _seed_link(db_session, code="redir02", target_url="https://example.com")

        await api_client.get(url="/redir02", follow_redirects=False)

        # Background tasks execute synchronously in the ASGI test transport
        repo: LinkRepository = LinkRepository(db_session)
        # Expire the cached instance so SQLAlchemy re-fetches from the DB
        await db_session.commit()
        updated: Link | None = await repo.get_by_code(code="redir02")
        assert updated is not None
        assert updated.clicks_count == 1

    async def test_inactive_link_returns_404(
        self,
        api_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """A GET on a soft-deleted (inactive) link returns 404."""
        await _seed_link(db_session, code="redir03", is_active=False)

        response: Response = await api_client.get(url="/redir03", follow_redirects=False)

        assert response.status_code == 404
        assert response.json()["error"] == "LINK_NOT_FOUND"

    async def test_nonexistent_code_returns_404(self, api_client: httpx.AsyncClient) -> None:
        """A GET on a code that does not exist returns 404."""
        response: Response = await api_client.get(url="/aaaaaaa", follow_redirects=False)

        assert response.status_code == 404
        assert response.json()["error"] == "LINK_NOT_FOUND"

    async def test_expired_link_returns_410(
        self,
        api_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """A GET on an expired link returns 410 Gone."""
        past: datetime = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
        await _seed_link(db_session, code="redir04", expires_at=past)

        response: Response = await api_client.get(url="/redir04", follow_redirects=False)

        assert response.status_code == 410
        assert response.json()["error"] == "LINK_EXPIRED"

    async def test_redirect_uses_307_not_301(
        self,
        api_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """The redirect uses 307 (temporary) to prevent browser caching per BC-5."""
        await _seed_link(db_session, code="redir05", target_url="https://example.com")

        response: Response = await api_client.get(url="/redir05", follow_redirects=False)

        assert response.status_code == 307
