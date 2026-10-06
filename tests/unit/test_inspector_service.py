# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for InspectorService.

Scope:
- Pure helper functions: _extract_title, _extract_description, _extract_image_url.
- InspectorService.dispatch_inspection: verifies the background task is scheduled
  with the correct callable and arguments.

No HTTP calls, no DB. Each helper test provides a raw HTML string and asserts
the extracted value. The dispatch test uses a mock scheduler.
"""

from __future__ import annotations

from unittest.mock import Mock

from fasturl.services.inspector_service import (
    InspectorService,
    _extract_description,
    _extract_image_url,
    _extract_title,
)

# ---------------------------------------------------------------------------
# _extract_title
# ---------------------------------------------------------------------------


class TestExtractTitle:
    """Tests for the <title> tag extractor."""

    def test_simple_title_is_extracted(self) -> None:
        """A standard <title> tag returns its text content."""
        html = "<html><head><title>Hello World</title></head></html>"
        assert _extract_title(html) == "Hello World"

    def test_title_with_whitespace_is_stripped(self) -> None:
        """Surrounding whitespace inside the title is stripped."""
        html = "<html><head><title>  Padded Title  </title></head></html>"
        assert _extract_title(html) == "Padded Title"

    def test_title_with_attributes_on_tag(self) -> None:
        """A <title> tag with extra attributes is still matched."""
        html = '<title lang="en">Attributed Title</title>'
        assert _extract_title(html) == "Attributed Title"

    def test_missing_title_returns_none(self) -> None:
        """HTML without a <title> tag returns None."""
        html = "<html><head></head><body>No title here</body></html>"
        assert _extract_title(html) is None

    def test_empty_html_returns_none(self) -> None:
        """An empty string returns None."""
        assert _extract_title("") is None


# ---------------------------------------------------------------------------
# _extract_description
# ---------------------------------------------------------------------------


class TestExtractDescription:
    """Tests for the OpenGraph / meta description extractor."""

    def test_og_description_is_preferred(self) -> None:
        """og:description is returned when present."""
        html = '<meta property="og:description" content="OG Desc"/><meta name="description" content="Meta Desc"/>'
        assert _extract_description(html) == "OG Desc"

    def test_meta_description_used_as_fallback(self) -> None:
        """meta description is used when og:description is absent."""
        html = '<meta name="description" content="Fallback Desc"/>'
        assert _extract_description(html) == "Fallback Desc"

    def test_description_with_whitespace_is_stripped(self) -> None:
        """Surrounding whitespace in the content attribute is stripped."""
        html = '<meta property="og:description" content="  Spaced  "/>'
        assert _extract_description(html) == "Spaced"

    def test_missing_description_returns_none(self) -> None:
        """HTML with no description meta tags returns None."""
        html = "<html><head><title>No desc</title></head></html>"
        assert _extract_description(html) is None

    def test_empty_html_returns_none(self) -> None:
        """An empty string returns None."""
        assert _extract_description("") is None


# ---------------------------------------------------------------------------
# _extract_image_url
# ---------------------------------------------------------------------------


class TestExtractImageUrl:
    """Tests for the og:image URL extractor."""

    def test_og_image_url_is_extracted(self) -> None:
        """og:image content attribute is returned correctly."""
        html = '<meta property="og:image" content="https://example.com/image.png"/>'
        assert _extract_image_url(html) == "https://example.com/image.png"

    def test_og_image_with_whitespace_is_stripped(self) -> None:
        """Surrounding whitespace in the content attribute is stripped."""
        html = '<meta property="og:image" content="  https://example.com/img.jpg  "/>'
        assert _extract_image_url(html) == "https://example.com/img.jpg"

    def test_missing_og_image_returns_none(self) -> None:
        """HTML without og:image returns None."""
        html = "<html><head><title>No image</title></head></html>"
        assert _extract_image_url(html) is None

    def test_empty_html_returns_none(self) -> None:
        """An empty string returns None."""
        assert _extract_image_url("") is None


# ---------------------------------------------------------------------------
# InspectorService.dispatch_inspection
# ---------------------------------------------------------------------------


class TestDispatchInspection:
    """Tests for the background task dispatch logic."""

    def test_dispatch_inspection_schedules_inspect_link_with_correct_args(self) -> None:
        """dispatch_inspection registers inspect_link on the scheduler with all kwargs."""
        import httpx

        http_client: httpx.AsyncClient = httpx.AsyncClient()
        inspector: InspectorService = InspectorService(http_client=http_client)
        mock_scheduler: Mock = Mock()
        mock_repository: Mock = Mock()

        inspector.dispatch_inspection(
            scheduler=mock_scheduler,
            code="abc1234",
            target_url="https://example.com",
            repository=mock_repository,
        )

        mock_scheduler.add_task.assert_called_once()
        call_kwargs = mock_scheduler.add_task.call_args.kwargs
        assert call_kwargs["code"] == "abc1234"
        assert call_kwargs["target_url"] == "https://example.com"
        assert call_kwargs["http_client"] is http_client
        assert call_kwargs["repository"] is mock_repository

    def test_dispatch_inspection_uses_http_client_from_inspector(self) -> None:
        """The http_client is sourced from the InspectorService, not passed by caller."""
        import httpx

        http_client: httpx.AsyncClient = httpx.AsyncClient()
        inspector: InspectorService = InspectorService(http_client=http_client)
        mock_scheduler: Mock = Mock()

        inspector.dispatch_inspection(
            scheduler=mock_scheduler,
            code="xyz9876",
            target_url="https://example.org",
            repository=Mock(),
        )

        assert mock_scheduler.add_task.call_args.kwargs["http_client"] is http_client
