# -----------------------------------------------------------------------------
# Copyright (c) 2025 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for InspectorService HTML extraction helpers.

Scope: pure functions _extract_title, _extract_description, _extract_image_url.
No HTTP calls, no DB. Each test provides a raw HTML string and asserts the
extracted value.
"""

from __future__ import annotations

from fasturl.services.inspector_service import (
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
