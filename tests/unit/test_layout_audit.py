from ingestion.layout_audit import (
    TextBlock,
    classify_location,
    find_repeated_candidates,
    normalize_block_text,
)


def test_normalize_block_text_collapses_whitespace_and_digits() -> None:
    assert normalize_block_text(" Member   Copy  123 ") == "member copy <n>"


def test_classify_location_detects_edges_and_body() -> None:
    assert classify_location(10, 10, 100, 50, 600, 800) == "top"
    assert classify_location(10, 760, 100, 790, 600, 800) == "bottom"
    assert classify_location(10, 200, 50, 250, 600, 800) == "left"
    assert classify_location(550, 200, 595, 250, 600, 800) == "right"
    assert classify_location(100, 200, 500, 600, 600, 800) == "body"


def test_find_repeated_candidates_requires_recurrence() -> None:
    blocks = [
        TextBlock(
            page_number=page,
            block_number=1,
            text="Member Copy",
            normalized_text="member copy",
            x0=550,
            y0=200,
            x1=595,
            y1=250,
            page_width=600,
            page_height=800,
            location="right",
        )
        for page in range(1, 11)
    ]
    blocks.append(
        TextBlock(
            page_number=1,
            block_number=2,
            text="Legitimate body content",
            normalized_text="legitimate body content",
            x0=100,
            y0=200,
            x1=500,
            y1=600,
            page_width=600,
            page_height=800,
            location="body",
        )
    )

    candidates = find_repeated_candidates(
        blocks,
        total_pages=10,
        minimum_pages=3,
        minimum_page_ratio=0.2,
    )

    assert len(candidates) == 1
    assert candidates[0].normalized_text == "member copy"
    assert "repeats_near_page_edge" in candidates[0].reasons
