import pytest

from app.source_view import (
    chunk_page_count,
    format_count,
    format_timestamp,
    page_range_label,
    source_option_label,
)


def test_source_view_formats_counts_and_pages() -> None:
    assert format_count(204783) == "204,783"
    assert format_count(None) == "0"
    assert page_range_label({"page_start": 4, "page_end": 7}) == "Pages 4-7"
    assert page_range_label({"page_start": 4, "page_end": 4}) == "Page 4"
    assert page_range_label({}) == "Page not recorded"


def test_source_view_formats_timestamp_safely() -> None:
    assert format_timestamp(None) == "Not available"
    assert format_timestamp("not-a-date") == "Not available"
    assert "2026-07-23" in format_timestamp("2026-07-23T22:00:00+00:00")


def test_chunk_page_count_is_bounded() -> None:
    assert chunk_page_count(0, 10) == 1
    assert chunk_page_count(293, 10) == 30
    with pytest.raises(ValueError):
        chunk_page_count(10, 0)


def test_source_option_label_uses_safe_metadata() -> None:
    assert (
        source_option_label(
            {
                "title": "BABOK Guide",
                "status": "ready",
                "chunk_count": 293,
            }
        )
        == "BABOK Guide · ready · 293 chunks"
    )
