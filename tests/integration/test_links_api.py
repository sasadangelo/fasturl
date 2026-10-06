# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Integration tests for the /api/v1/links management endpoints.

Boundary: FastAPI ASGI transport → real router → real service → real
repository → in-memory SQLite. Background inspection is invoked directly
as a coroutine; the outbound httpx call is replaced by a mock transport.

Covers:
  POST   /api/v1/links              (JS-001, JS-002)
  GET    /api/v1/links              (JS-004)
  GET    /api/v1/links/{code}       (JS-003)
  DELETE /api/v1/links/{code}       (JS-005)
  POST   /api/v1/links/{code}/inspect (JS-008)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import httpx
from httpx._client import AsyncClient
from httpx._models import Response
from sqlalchemy.ext.asyncio import AsyncSession

from fasturl.models.link import LinkDAO
from fasturl.repositories.link_repository import LinkRepository
from fasturl.services.inspector_service import inspect_link

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _future_iso() -> str:
    """Return an ISO 8601 datetime 30 days from now (UTC, timezone-aware)."""
    return (datetime.now(tz=timezone.utc) + timedelta(days=30)).isoformat()


# ---------------------------------------------------------------------------
# POST /api/v1/links
# ---------------------------------------------------------------------------


class TestCreateLink:
    """JS-001 / JS-002 — create shortened links."""

    async def test_auto_code_returns_201(self, api_client: httpx.AsyncClient) -> None:
        """A valid payload without custom_code returns 201 with a generated code."""
        response: Response = await api_client.post(
            url="/api/v1/links",
            json={"target_url": "https://example.com/article"},
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["code"]) == 7
        assert data["inspection"]["status"] == "pending_analysis"
        assert data["metrics"]["clicks_count"] == 0

    async def test_custom_alias_returns_201(self, api_client: httpx.AsyncClient) -> None:
        """A valid payload with custom_code returns 201 bound to that code."""
        response: Response = await api_client.post(
            url="/api/v1/links",
            json={"target_url": "https://example.com", "custom_code": "mybrand1"},
        )
        assert response.status_code == 201
        assert response.json()["code"] == "mybrand1"

    async def test_duplicate_alias_returns_409(self, api_client: httpx.AsyncClient) -> None:
        """Creating a link with an already-used custom alias returns 409."""
        payload: dict[str, str] = {"target_url": "https://example.com", "custom_code": "mybrand2"}
        await api_client.post(url="/api/v1/links", json=payload)
        response = await api_client.post(url="/api/v1/links", json=payload)
        assert response.status_code == 409
        assert response.json()["error"] == "ALIAS_ALREADY_TAKEN"

    async def test_invalid_url_scheme_returns_400(self, api_client: httpx.AsyncClient) -> None:
        """A target URL with an unsupported scheme (ftp) returns 400.

        FastAPI's global RequestValidationError handler normalises 422 → 400.
        """
        response: Response = await api_client.post(
            url="/api/v1/links",
            json={"target_url": "ftp://example.com/file"},
        )
        assert response.status_code == 400
        assert response.json()["error"] == "VALIDATION_ERROR"

    async def test_self_redirect_returns_400(self, api_client: httpx.AsyncClient) -> None:
        """A target URL pointing at the service itself returns 400."""
        response: Response = await api_client.post(
            url="/api/v1/links",
            json={"target_url": "http://localhost:8000/some/path"},
        )
        assert response.status_code == 400
        assert response.json()["error"] == "VALIDATION_ERROR"

    async def test_past_expiry_returns_400(self, api_client: httpx.AsyncClient) -> None:
        """A payload with expires_at in the past returns 400.

        FastAPI's global RequestValidationError handler normalises 422 → 400.
        """
        past: str = (datetime.now(tz=timezone.utc) - timedelta(days=1)).isoformat()
        response: Response = await api_client.post(
            url="/api/v1/links",
            json={"target_url": "https://example.com", "expires_at": past},
        )
        assert response.status_code == 400
        assert response.json()["error"] == "VALIDATION_ERROR"

    async def test_invalid_alias_chars_returns_400(self, api_client: httpx.AsyncClient) -> None:
        """A custom alias containing special characters returns 400.

        FastAPI's global RequestValidationError handler normalises 422 → 400.
        """
        response: Response = await api_client.post(
            url="/api/v1/links",
            json={"target_url": "https://example.com", "custom_code": "bad alias!"},
        )
        assert response.status_code == 400
        assert response.json()["error"] == "VALIDATION_ERROR"

    async def test_future_expiry_is_accepted(self, api_client: httpx.AsyncClient) -> None:
        """A valid payload with a future expires_at returns 201."""
        response: Response = await api_client.post(
            url="/api/v1/links",
            json={"target_url": "https://example.com", "expires_at": _future_iso()},
        )
        assert response.status_code == 201
        assert response.json()["expires_at"] is not None

    async def test_response_contains_error_envelope_on_failure(self, api_client: httpx.AsyncClient) -> None:
        """Error responses follow the standardised envelope schema."""
        response: Response = await api_client.post(
            url="/api/v1/links",
            json={"target_url": "http://localhost:8000/loop"},
        )
        body = response.json()
        assert body["success"] is False
        assert "error" in body
        assert "details" in body


# ---------------------------------------------------------------------------
# GET /api/v1/links
# ---------------------------------------------------------------------------


class TestListLinks:
    """JS-004 — list and filter shortened links."""

    async def test_empty_collection_returns_empty_list(self, api_client: httpx.AsyncClient) -> None:
        """With no links in the DB the endpoint returns an empty array."""
        response: Response = await api_client.get(url="/api/v1/links")
        assert response.status_code == 200
        assert response.json() == []

    async def test_created_link_appears_in_list(self, api_client: httpx.AsyncClient) -> None:
        """A link created via POST appears in the subsequent GET list."""
        await api_client.post("/api/v1/links", json={"target_url": "https://example.com"})
        response: Response = await api_client.get(url="/api/v1/links")
        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_filter_by_status_returns_matching_links(
        self,
        api_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Filtering by status=active returns only active links."""
        # Create a link then manually push it to 'active' via the repository
        post_resp: Response = await api_client.post(url="/api/v1/links", json={"target_url": "https://example.com"})
        code = post_resp.json()["code"]
        repo: LinkRepository = LinkRepository(session=db_session)
        await repo.update_inspection(
            code,
            status="active",
            http_status_code=200,
            latency_ms=50.0,
            title="Example",
            description=None,
            image_url=None,
        )

        response: Response = await api_client.get(url="/api/v1/links?status=active")
        assert response.status_code == 200
        statuses = [item["inspection"]["status"] for item in response.json()]
        assert all(s == "active" for s in statuses)

    async def test_filter_by_invalid_status_returns_400(self, api_client: httpx.AsyncClient) -> None:
        """Requesting an unsupported status value returns 400."""
        response: Response = await api_client.get(url="/api/v1/links?status=bogus")
        assert response.status_code == 400
        assert response.json()["error"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# GET /api/v1/links/{code}
# ---------------------------------------------------------------------------


class TestGetLink:
    """JS-003 — retrieve a single link by code."""

    async def test_existing_code_returns_200(self, api_client: httpx.AsyncClient) -> None:
        """A known code returns 200 with the full link payload."""
        post_resp: Response = await api_client.post(url="/api/v1/links", json={"target_url": "https://example.com"})
        code = post_resp.json()["code"]

        response: Response = await api_client.get(url=f"/api/v1/links/{code}")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == code
        assert "inspection" in data
        assert "metrics" in data

    async def test_nonexistent_code_returns_404(self, api_client: httpx.AsyncClient) -> None:
        """A code that does not exist returns 404 with LINK_NOT_FOUND."""
        response: Response = await api_client.get(url="/api/v1/links/aaaaaaa")
        assert response.status_code == 404
        assert response.json()["error"] == "LINK_NOT_FOUND"


# ---------------------------------------------------------------------------
# DELETE /api/v1/links/{code}
# ---------------------------------------------------------------------------


class TestDeleteLink:
    """JS-005 — soft-delete a link."""

    async def test_existing_link_returns_204(self, api_client: httpx.AsyncClient) -> None:
        """Deleting an existing link returns 204 No Content."""
        post_resp: Response = await api_client.post(url="/api/v1/links", json={"target_url": "https://example.com"})
        code = post_resp.json()["code"]

        response: Response = await api_client.delete(url=f"/api/v1/links/{code}")
        assert response.status_code == 204

    async def test_nonexistent_link_returns_404(self, api_client: httpx.AsyncClient) -> None:
        """Deleting a non-existent code returns 404."""
        response: Response = await api_client.delete(url="/api/v1/links/aaaaaaa")
        assert response.status_code == 404
        assert response.json()["error"] == "LINK_NOT_FOUND"

    async def test_deleted_link_no_longer_active(self, api_client: httpx.AsyncClient) -> None:
        """After soft-delete, the link is inactive (GET returns is_active=false)."""
        post_resp: Response = await api_client.post(url="/api/v1/links", json={"target_url": "https://example.com"})
        code = post_resp.json()["code"]
        await api_client.delete(url=f"/api/v1/links/{code}")

        get_resp: Response = await api_client.get(url=f"/api/v1/links/{code}")
        assert get_resp.status_code == 200
        assert get_resp.json()["is_active"] is False


# ---------------------------------------------------------------------------
# POST /api/v1/links/{code}/inspect
# ---------------------------------------------------------------------------


class TestTriggerInspection:
    """JS-008 — manual re-inspection trigger."""

    async def test_existing_link_returns_202(self, api_client: httpx.AsyncClient) -> None:
        """Triggering re-inspection on an existing link returns 202."""
        post_resp: Response = await api_client.post(url="/api/v1/links", json={"target_url": "https://example.com"})
        code = post_resp.json()["code"]

        response: Response = await api_client.post(url=f"/api/v1/links/{code}/inspect")
        assert response.status_code == 202

    async def test_inspection_status_reset_to_pending(self, api_client: httpx.AsyncClient) -> None:
        """After triggering re-inspection the status is reset to pending_analysis."""
        post_resp: Response = await api_client.post(url="/api/v1/links", json={"target_url": "https://example.com"})
        code = post_resp.json()["code"]

        response: Response = await api_client.post(url=f"/api/v1/links/{code}/inspect")
        assert response.json()["inspection"]["status"] == "pending_analysis"

    async def test_nonexistent_link_returns_404(self, api_client: httpx.AsyncClient) -> None:
        """Triggering re-inspection on a missing code returns 404."""
        response: Response = await api_client.post(url="/api/v1/links/aaaaaaa/inspect")
        assert response.status_code == 404
        assert response.json()["error"] == "LINK_NOT_FOUND"

    async def test_already_pending_is_accepted_idempotent(self, api_client: httpx.AsyncClient) -> None:
        """Re-triggering when status is already pending_analysis still returns 202."""
        post_resp: Response = await api_client.post(url="/api/v1/links", json={"target_url": "https://example.com"})
        code = post_resp.json()["code"]
        # LinkDAO starts in pending_analysis — trigger again
        response: Response = await api_client.post(url=f"/api/v1/links/{code}/inspect")
        assert response.status_code == 202


# ---------------------------------------------------------------------------
# Background inspection (direct coroutine invocation)
# ---------------------------------------------------------------------------


class TestInspectLinkDirect:
    """JS-007 — background inspector updates DB state after coroutine completes."""

    async def test_successful_inspection_sets_active(self, db_session: AsyncSession) -> None:
        """A reachable target URL sets inspection_status to 'active' in the DB."""
        # Seed a link directly
        from datetime import datetime

        from fasturl.models.link import LinkDAO

        link: LinkDAO = LinkDAO(
            code="insp001",
            target_url="https://example.com",
            is_active=True,
            inspection_status="pending_analysis",
            clicks_count=0,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db_session.add(instance=link)
        await db_session.commit()

        # Build a mock HTTP response that simulates a successful 200 HTML page
        html_body = "<html><head><title>Example</title></head></html>"
        mock_response: Response = httpx.Response(status_code=200, text=html_body)
        mock_client: AsyncClient = httpx.AsyncClient(transport=httpx.MockTransport(handler=lambda req: mock_response))
        repo: LinkRepository = LinkRepository(session=db_session)

        await inspect_link(
            code="insp001",
            target_url="https://example.com",
            http_client=mock_client,
            repository=repo,
        )
        await mock_client.aclose()

        updated: LinkDAO | None = await repo.get_by_code(code="insp001")
        assert updated is not None
        assert updated.inspection_status == "active"
        assert updated.title == "Example"
        assert updated.http_status_code == 200

    async def test_unreachable_target_sets_unreachable(self, db_session: AsyncSession) -> None:
        """A timeout or request error sets inspection_status to 'unreachable'."""
        from datetime import datetime

        from fasturl.models.link import LinkDAO

        link = LinkDAO(
            code="insp002",
            target_url="https://unreachable.example",
            is_active=True,
            inspection_status="pending_analysis",
            clicks_count=0,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db_session.add(instance=link)
        await db_session.commit()

        def _raise_timeout(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout(message="timeout", request=request)

        mock_client: AsyncClient = httpx.AsyncClient(transport=httpx.MockTransport(handler=_raise_timeout))
        repo: LinkRepository = LinkRepository(session=db_session)

        await inspect_link(
            code="insp002",
            target_url="https://unreachable.example",
            http_client=mock_client,
            repository=repo,
        )
        await mock_client.aclose()

        updated: LinkDAO | None = await repo.get_by_code(code="insp002")
        assert updated is not None
        assert updated.inspection_status == "unreachable"
