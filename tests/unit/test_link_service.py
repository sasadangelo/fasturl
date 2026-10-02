# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for LinkService business logic.

Scope: pure domain rules — code generation, self-redirect guard, expiry
enforcement, sort validation, collision retry. No real DB, no HTTP calls.
The LinkRepository is replaced by an AsyncMock.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from fasturl.api.schemas.link_schemas import LinkResponse
from fasturl.core.exceptions import AliasAlreadyTakenError, LinkNotFoundError, ValidationError
from fasturl.models.link import Link
from fasturl.services.link_service import LinkService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_link(
    code: str = "abcdefg",
    target_url: str = "https://example.com",
    is_active: bool = True,
    expires_at: datetime | None = None,
    inspection_status: str = "pending_analysis",
    clicks_count: int = 0,
) -> Link:
    """Build a minimal Link ORM instance for use in unit tests."""
    now: datetime = datetime.now(tz=UTC).replace(tzinfo=None)
    return Link(
        id=1,
        code=code,
        target_url=target_url,
        is_active=is_active,
        expires_at=expires_at,
        inspection_status=inspection_status,
        clicks_count=clicks_count,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# _validate_target_url
# ---------------------------------------------------------------------------


class TestValidateTargetUrl:
    """Tests for the self-redirect prevention rule."""

    def test_self_redirect_raises_validation_error(self, mock_repository: AsyncMock) -> None:
        """A target URL that starts with the service base URL is rejected."""
        service: LinkService = LinkService(repository=mock_repository)
        # settings.app.base_url defaults to "http://localhost:8000"
        with pytest.raises(ValidationError) as exc_info:
            service._validate_target_url(target_url="http://localhost:8000/some/path")
        assert "self-redirect" in exc_info.value.details[0]

    def test_external_url_passes(self, mock_repository: AsyncMock) -> None:
        """An external URL passes validation without raising."""
        service: LinkService = LinkService(repository=mock_repository)
        service._validate_target_url(target_url="https://example.com/page")  # must not raise


# ---------------------------------------------------------------------------
# create_link — custom alias collision
# ---------------------------------------------------------------------------


class TestCreateLinkAliasCollision:
    """Tests for the custom alias uniqueness rule."""

    async def test_duplicate_alias_raises_alias_already_taken(self, mock_repository: AsyncMock) -> None:
        """If the custom alias already exists, AliasAlreadyTakenError is raised."""
        mock_repository.code_exists.return_value = True
        service: LinkService = LinkService(repository=mock_repository)

        with pytest.raises(AliasAlreadyTakenError) as exc_info:
            await service.create_link(
                target_url="https://example.com",
                custom_code="mybrand1",
                expires_at=None,
            )
        assert "mybrand1" in exc_info.value.details[0]

    async def test_new_alias_is_persisted(self, mock_repository: AsyncMock) -> None:
        """A new unique alias is passed straight through to the repository."""
        link: Link = _make_link(code="mybrand1")
        mock_repository.code_exists.return_value = False
        mock_repository.create.return_value = link
        service: LinkService = LinkService(repository=mock_repository)

        result: LinkResponse = await service.create_link(
            target_url="https://example.com",
            custom_code="mybrand1",
            expires_at=None,
        )

        mock_repository.create.assert_called_once()
        assert result.code == "mybrand1"


# ---------------------------------------------------------------------------
# create_link — collision retry for auto-generated codes
# ---------------------------------------------------------------------------


class TestCreateLinkCollisionRetry:
    """Tests for the Base62 code collision retry loop."""

    async def test_retries_until_unique_code_found(self, mock_repository: AsyncMock) -> None:
        """Repository is called again after a collision on an auto-generated code."""
        link = _make_link(code="abcdefg")
        # First two candidates collide; third succeeds
        mock_repository.code_exists.side_effect = [True, True, False]
        mock_repository.create.return_value = link
        service: LinkService = LinkService(repository=mock_repository)

        result: LinkResponse = await service.create_link(
            target_url="https://example.com",
            custom_code=None,
            expires_at=None,
        )

        assert mock_repository.code_exists.call_count == 3
        assert result.code == "abcdefg"

    async def test_exceeding_max_retries_raises_validation_error(self, mock_repository: AsyncMock) -> None:
        """If all retry attempts collide, ValidationError is raised."""
        mock_repository.code_exists.return_value = True  # always collides
        service: LinkService = LinkService(repository=mock_repository)

        with pytest.raises(ValidationError) as exc_info:
            await service.create_link(
                target_url="https://example.com",
                custom_code=None,
                expires_at=None,
            )
        assert "unique short code" in exc_info.value.details[0]


# ---------------------------------------------------------------------------
# get_link
# ---------------------------------------------------------------------------


class TestGetLink:
    """Tests for retrieving a single link by code."""

    async def test_existing_code_returns_response(self, mock_repository: AsyncMock) -> None:
        """A known code returns a populated LinkResponse."""
        mock_repository.get_by_code.return_value = _make_link(code="abcdefg")
        service: LinkService = LinkService(repository=mock_repository)

        result: LinkResponse = await service.get_link(code="abcdefg")

        assert result.code == "abcdefg"

    async def test_missing_code_raises_link_not_found(self, mock_repository: AsyncMock) -> None:
        """A code that does not exist raises LinkNotFoundError."""
        mock_repository.get_by_code.return_value = None
        service: LinkService = LinkService(repository=mock_repository)

        with pytest.raises(LinkNotFoundError):
            await service.get_link(code="xxxxxxx")


# ---------------------------------------------------------------------------
# delete_link
# ---------------------------------------------------------------------------


class TestDeleteLink:
    """Tests for soft-deleting a link."""

    async def test_existing_link_is_deleted(self, mock_repository: AsyncMock) -> None:
        """Deleting an existing link succeeds without raising."""
        mock_repository.soft_delete.return_value = True
        service: LinkService = LinkService(repository=mock_repository)

        await service.delete_link(code="abcdefg")  # must not raise

        mock_repository.soft_delete.assert_called_once_with("abcdefg")

    async def test_missing_link_raises_link_not_found(self, mock_repository: AsyncMock) -> None:
        """Soft-deleting a non-existent link raises LinkNotFoundError."""
        mock_repository.soft_delete.return_value = False
        service: LinkService = LinkService(repository=mock_repository)

        with pytest.raises(LinkNotFoundError):
            await service.delete_link(code="xxxxxxx")


# ---------------------------------------------------------------------------
# list_links — sort field validation
# ---------------------------------------------------------------------------


class TestListLinks:
    """Tests for the sort field validation in list_links."""

    async def test_invalid_sort_field_raises_validation_error(self, mock_repository: AsyncMock) -> None:
        """An unrecognised sort field raises ValidationError."""
        service: LinkService = LinkService(repository=mock_repository)

        with pytest.raises(ValidationError) as exc_info:
            await service.list_links(status=None, is_active=True, sort="invalid_field")
        assert "sort" in exc_info.value.details[0]

    async def test_valid_sort_field_passes(self, mock_repository: AsyncMock) -> None:
        """A valid sort field delegates to the repository without raising."""
        mock_repository.list_links.return_value = []
        service: LinkService = LinkService(repository=mock_repository)

        result: list[LinkResponse] = await service.list_links(status=None, is_active=True, sort="-created_at")

        mock_repository.list_links.assert_called_once()
        assert result == []


# ---------------------------------------------------------------------------
# resolve_for_redirect
# ---------------------------------------------------------------------------


class TestResolveForRedirect:
    """Tests for redirect resolution — active/inactive/expired links."""

    async def test_active_link_returns_target_url(self, mock_repository: AsyncMock) -> None:
        """An active, non-expired link resolves to its target URL."""
        mock_repository.get_by_code.return_value = _make_link(target_url="https://example.com")
        service: LinkService = LinkService(repository=mock_repository)

        result: str = await service.resolve_for_redirect(code="abcdefg")

        assert result == "https://example.com"

    async def test_inactive_link_raises_link_not_found(self, mock_repository: AsyncMock) -> None:
        """An inactive (soft-deleted) link raises LinkNotFoundError."""
        mock_repository.get_by_code.return_value = _make_link(is_active=False)
        service: LinkService = LinkService(repository=mock_repository)

        with pytest.raises(LinkNotFoundError):
            await service.resolve_for_redirect("abcdefg")

    async def test_nonexistent_code_raises_link_not_found(self, mock_repository: AsyncMock) -> None:
        """A code that does not exist raises LinkNotFoundError."""
        mock_repository.get_by_code.return_value = None
        service: LinkService = LinkService(repository=mock_repository)

        with pytest.raises(LinkNotFoundError):
            await service.resolve_for_redirect(code="xxxxxxx")

    async def test_expired_link_raises_link_expired(self, mock_repository: AsyncMock) -> None:
        """A link whose expires_at is in the past raises LinkExpiredError."""
        from fasturl.core.exceptions import LinkExpiredError

        past: datetime = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
        mock_repository.get_by_code.return_value = _make_link(expires_at=past)
        service: LinkService = LinkService(repository=mock_repository)

        with pytest.raises(LinkExpiredError):
            await service.resolve_for_redirect(code="abcdefg")

    async def test_future_expiry_does_not_raise(self, mock_repository: AsyncMock) -> None:
        """A link whose expires_at is in the future resolves normally."""
        future: datetime = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
        mock_repository.get_by_code.return_value = _make_link(
            target_url="https://example.com",
            expires_at=future,
        )
        service: LinkService = LinkService(repository=mock_repository)

        result: str = await service.resolve_for_redirect(code="abcdefg")

        assert result == "https://example.com"


# ---------------------------------------------------------------------------
# trigger_reinspection
# ---------------------------------------------------------------------------


class TestTriggerReinspection:
    """Tests for resetting inspection state."""

    async def test_existing_link_resets_and_returns_response(self, mock_repository: AsyncMock) -> None:
        """Re-inspection on an existing link resets status and returns updated snapshot."""
        link: Link = _make_link(code="abcdefg", inspection_status="pending_analysis")
        mock_repository.get_by_code.return_value = link
        mock_repository.reset_inspection.return_value = True
        service: LinkService = LinkService(repository=mock_repository)

        result: LinkResponse = await service.trigger_reinspection(code="abcdefg")

        mock_repository.reset_inspection.assert_called_once_with("abcdefg")
        assert result.inspection.status == "pending_analysis"

    async def test_nonexistent_link_raises_link_not_found(self, mock_repository: AsyncMock) -> None:
        """Re-inspection on a non-existent code raises LinkNotFoundError."""
        mock_repository.get_by_code.return_value = None
        service: LinkService = LinkService(repository=mock_repository)

        with pytest.raises(LinkNotFoundError):
            await service.trigger_reinspection(code="xxxxxxx")
