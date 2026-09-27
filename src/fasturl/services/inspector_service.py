# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Background URL inspection service.

Performs an async HTTP health check and OpenGraph/HTML metadata extraction on
a target URL. Invoked as a FastAPI ``BackgroundTask`` — never blocks the
request/response cycle.

Design decisions (from docs/domain-design.md):
- Decoupled from the HTTP layer: no FastAPI imports.
- Uses a shared ``httpx.AsyncClient`` instance (created in lifespan) to avoid
  per-task TCP connection overhead.
- Idempotent: safe to re-trigger on any link regardless of current status.
"""

from __future__ import annotations

import re
import time

import httpx
from loguru import logger

from fasturl.repositories.link_repository import LinkRepository

_log = logger.bind(name="InspectorService")

# Lightweight regex-based extractors — avoids a full HTML parser dependency
_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE | re.DOTALL)
_OG_DESCRIPTION_RE = re.compile(
    r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_META_DESCRIPTION_RE = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def _extract_title(html: str) -> str | None:
    """Extract the HTML ``<title>`` from a page body.

    Args:
        html: Raw HTML string.

    Returns:
        Stripped title text, or ``None`` if not found.
    """
    m = _TITLE_RE.search(html)
    return m.group(1).strip() if m else None


def _extract_description(html: str) -> str | None:
    """Extract OpenGraph or fallback meta description.

    Args:
        html: Raw HTML string.

    Returns:
        Stripped description text, or ``None`` if not found.
    """
    m = _OG_DESCRIPTION_RE.search(html) or _META_DESCRIPTION_RE.search(html)
    return m.group(1).strip() if m else None


def _extract_image_url(html: str) -> str | None:
    """Extract the OpenGraph image URL.

    Args:
        html: Raw HTML string.

    Returns:
        Stripped og:image URL, or ``None`` if not found.
    """
    m = _OG_IMAGE_RE.search(html)
    return m.group(1).strip() if m else None


async def inspect_link(
    code: str,
    target_url: str,
    http_client: httpx.AsyncClient,
    repository: LinkRepository,
) -> None:
    """Perform a background HTTP inspection and persist the results.

    Measures latency, records the HTTP status code, and extracts page metadata.
    On any error (timeout, DNS failure, non-2xx response) the status is set to
    ``"unreachable"``. This function is idempotent and safe to retry.

    Args:
        code: The Base62 code of the link being inspected.
        target_url: The destination URL to inspect.
        http_client: Shared async HTTP client from ``app.state``.
        repository: Data-access layer for persisting inspection results.
    """
    _log.info(f"Starting inspection for link '{code}' → {target_url}")

    status = "unreachable"
    http_status_code: int | None = None
    latency_ms: float | None = None
    title: str | None = None
    description: str | None = None
    image_url: str | None = None

    start = time.monotonic()
    try:
        response = await http_client.get(target_url)
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        http_status_code = response.status_code

        if response.is_success or response.is_redirect:
            status = "active"
            html = response.text
            title = _extract_title(html)
            description = _extract_description(html)
            image_url = _extract_image_url(html)
        else:
            status = "unreachable"

        _log.info(f"Inspection complete for '{code}': status={status}, http={http_status_code}, latency={latency_ms}ms")

    except httpx.TimeoutException:
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        _log.warning(f"Inspection timeout for '{code}' after {latency_ms}ms")

    except httpx.RequestError as exc:
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        _log.warning(f"Inspection request error for '{code}': {exc}")

    await repository.update_inspection(
        code,
        status=status,
        http_status_code=http_status_code,
        latency_ms=latency_ms,
        title=title,
        description=description,
        image_url=image_url,
    )
