# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Business logic service for the Link aggregate.

This service is the brain of the application. It enforces all domain invariants,
orchestrates repositories, generates short codes, and validates inputs.

Hard rules (from docs/architecture.md):
- Zero knowledge of HTTP / FastAPI.
- No imports of ``fastapi``, ``Request``, ``Response``, or ``HTTPException``.
- Raises pure domain exceptions (``LinkNotFoundError``, etc.).
"""

from __future__ import annotations

import random
import string
from datetime import datetime
from typing import LiteralString

from loguru import logger

from fasturl.api.schemas.link_schemas import LinkResponse
from fasturl.core.config import settings
from fasturl.core.exceptions import AliasAlreadyTakenError, LinkNotFoundError, ValidationError
from fasturl.models.link import Link
from fasturl.repositories.link_repository import LinkRepository

_log = logger.bind(name="LinkService")

# Base62 alphabet — URL-safe, no special characters
_BASE62_ALPHABET: LiteralString = string.ascii_letters + string.digits
_MAX_CODE_RETRIES = 10


def _build_short_url(code: str) -> str:
    """Construct the full short URL from a code.

    Args:
        code: The Base62 short code or custom alias.

    Returns:
        Fully-qualified short URL (e.g. ``http://127.0.0.1:8000/aB3x9zK``).
    """
    base = settings.app.base_url.rstrip("/")
    return f"{base}/{code}"


def _orm_to_response(link: Link) -> LinkResponse:
    """Convert a ``Link`` ORM instance into a ``LinkResponse`` DTO.

    Args:
        link: The ORM ``Link`` instance.

    Returns:
        A ``LinkResponse`` DTO ready for serialisation.
    """
    from fasturl.api.schemas.link_schemas import InspectionResponse, MetricsResponse

    return LinkResponse(
        code=link.code,
        short_url=_build_short_url(link.code),
        target_url=link.target_url,
        is_active=link.is_active,
        expires_at=link.expires_at,
        inspection=InspectionResponse(
            status=link.inspection_status,
            http_status_code=link.http_status_code,
            latency_ms=link.latency_ms,
            title=link.title,
            description=link.description,
            image_url=link.image_url,
            last_checked_at=link.last_checked_at,
        ),
        metrics=MetricsResponse(
            clicks_count=link.clicks_count,
            last_clicked_at=link.last_clicked_at,
        ),
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


class LinkService:
    """Application service for all Link aggregate operations.

    Args:
        repository: Data-access layer injected via ``Depends``.
    """

    def __init__(self, repository: LinkRepository) -> None:
        self._repository = repository

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_code(self) -> str:
        """Generate a random Base62 code of the configured length.

        Returns:
            A random alphanumeric string of ``settings.app.code_length`` characters.
        """
        length = settings.app.code_length
        return "".join(random.choices(_BASE62_ALPHABET, k=length))

    def _validate_target_url(self, target_url: str) -> None:
        """Enforce self-redirect prevention and scheme validation.

        The Pydantic schema already validates scheme and URL syntax. This method
        adds the domain-level rule: the target URL must not point back to the
        FastURL base URL (self-redirect loop prevention).

        Args:
            target_url: The raw target URL string.

        Raises:
            ValidationError: If the target URL equals the application base URL.
        """
        base = settings.app.base_url.rstrip("/").lower()
        if target_url.lower().startswith(base):
            raise ValidationError(["target_url -> URL must not point back to this service (self-redirect)"])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_link(
        self,
        target_url: str,
        custom_code: str | None,
        expires_at: datetime | None,
    ) -> LinkResponse:
        """Create a new shortened link.

        Generates a Base62 code (or validates the custom alias), enforces domain
        invariants, and persists the new Link aggregate.

        Args:
            target_url: Validated destination URL (HTTP/HTTPS).
            custom_code: Optional custom alias (pre-validated by Pydantic schema).
            expires_at: Optional expiration datetime (pre-validated to be in the future).

        Returns:
            A ``LinkResponse`` DTO for the newly created link.

        Raises:
            AliasAlreadyTakenError: If ``custom_code`` is already in use.
            ValidationError: If the target URL is a self-redirect.
        """
        self._validate_target_url(target_url)

        if custom_code is not None:
            if await self._repository.code_exists(code=custom_code):
                raise AliasAlreadyTakenError(alias=custom_code)
            code: str = custom_code
        else:
            # Collision-retry loop for auto-generated codes
            for _ in range(_MAX_CODE_RETRIES):
                candidate = self._generate_code()
                if not await self._repository.code_exists(code=candidate):
                    code = candidate
                    break
            else:
                _log.error("Failed to generate a unique code after max retries")
                raise ValidationError(["code -> Could not generate a unique short code. Please try again."])

        now: datetime = datetime.utcnow()
        link: Link = Link(
            code=code,
            target_url=target_url,
            is_active=True,
            expires_at=expires_at,
            inspection_status="pending_analysis",
            clicks_count=0,
            created_at=now,
            updated_at=now,
        )
        persisted: Link = await self._repository.create(link)
        _log.info(f"Link created: code='{code}', target='{target_url}'")
        return _orm_to_response(link=persisted)

    async def get_link(self, code: str) -> LinkResponse:
        """Retrieve the full details of a single link by code.

        Args:
            code: The Base62 short code or custom alias.

        Returns:
            A ``LinkResponse`` DTO.

        Raises:
            LinkNotFoundError: If no link exists with the given code.
        """
        link: Link | None = await self._repository.get_by_code(code)
        if link is None:
            raise LinkNotFoundError(code)
        return _orm_to_response(link)

    async def list_links(
        self,
        status: str | None,
        is_active: bool | None,
        sort: str,
    ) -> list[LinkResponse]:
        """Return all links with optional filtering and sorting.

        Args:
            status: Filter by inspection status.
            is_active: Filter by operational state.
            sort: Sort expression (e.g. ``"-created_at"``); prefix ``-`` = descending.

        Returns:
            List of ``LinkResponse`` DTOs.

        Raises:
            ValidationError: If an unsupported sort field is provided.
        """
        _valid_sort_fields: set[str] = {"created_at", "clicks_count"}
        sort_desc: bool = sort.startswith("-")
        sort_field: str = sort.lstrip("-")

        if sort_field not in _valid_sort_fields:
            raise ValidationError(details=[f"sort -> Must be one of: {', '.join(_valid_sort_fields)}"])

        links: list[Link] = await self._repository.list_links(
            status=status,
            is_active=is_active,
            sort_field=sort_field,
            sort_desc=sort_desc,
        )
        return [_orm_to_response(link) for link in links]

    async def delete_link(self, code: str) -> None:
        """Soft-delete (disable) a link by code.

        Args:
            code: The Base62 short code or custom alias.

        Raises:
            LinkNotFoundError: If no link exists with the given code.
        """
        deleted: bool = await self._repository.soft_delete(code)
        if not deleted:
            raise LinkNotFoundError(code)
        _log.info(f"Link soft-deleted: code='{code}'")

    async def trigger_reinspection(self, code: str) -> LinkResponse:
        """Reset inspection state to ``pending_analysis`` and return the current snapshot.

        Args:
            code: The Base62 short code or custom alias.

        Returns:
            A ``LinkResponse`` DTO reflecting the reset inspection state.

        Raises:
            LinkNotFoundError: If no link exists with the given code.
        """
        link: Link | None = await self._repository.get_by_code(code)
        if link is None:
            raise LinkNotFoundError(code)

        await self._repository.reset_inspection(code)

        # Re-fetch to get the up-to-date snapshot after reset
        updated: Link | None = await self._repository.get_by_code(code)
        assert updated is not None  # noqa: S101 — impossible after successful get above
        _log.info(f"Re-inspection triggered for link '{code}'")
        return _orm_to_response(link=updated)

    async def resolve_for_redirect(self, code: str) -> str:
        """Resolve a short code to its target URL, enforcing is_active and expiry rules.

        Args:
            code: The Base62 short code or custom alias.

        Returns:
            The target URL string if the link is active and not expired.

        Raises:
            LinkNotFoundError: If the code does not exist or ``is_active`` is ``False``.
            LinkExpiredError: If the link's ``expires_at`` is in the past.
        """
        from fasturl.core.exceptions import LinkExpiredError

        link: Link | None = await self._repository.get_by_code(code)

        if link is None or not link.is_active:
            raise LinkNotFoundError(code)

        if link.expires_at is not None:
            expires = link.expires_at.replace(tzinfo=None) if link.expires_at.tzinfo else link.expires_at
            if datetime.utcnow() > expires:
                raise LinkExpiredError(code, expired_at=link.expires_at.isoformat())

        return link.target_url
