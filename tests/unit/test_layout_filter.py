from pathlib import Path

from ingestion.layout_audit import TextBlock
from ingestion.layout_filter import (
    LayoutFilterPolicy,
    build_layout_filter_policy,
    filter_blocks,
    is_printed_page_number,
    removal_reason,
)


def make_block(
    *,
    page_number: int,
    text: str,
    normalized_text: str,
    location: str,
    x0: float = 10,
    y0: float = 200,
    x1: float = 30,
    y1: float = 300,
    page_width: float = 600,
    page_height: float = 800,
) -> TextBlock:
    return TextBlock(
        page_number=page_number,
        block_number=1,
        text=text,
        normalized_text=normalized_text,
        x0=x0,
        y0=y0,
        x1=x1,
        y1=y1,
        page_width=page_width,
        page_height=page_height,
        location=location,
    )


def test_policy_learns_only_near_universal_edge_text(
    monkeypatch,
    tmp_path: Path,
) -> None:
    watermark = "complimentary member copy"
    blocks = [
        make_block(
            page_number=page,
            text="Complimentary Member Copy",
            normalized_text=watermark,
            location="left",
        )
        for page in range(1, 101)
    ]
    blocks.extend(
        make_block(
            page_number=page,
            text="3.1.2 Description",
            normalized_text="3.1.2 description",
            location="body",
        )
        for page in range(1, 21)
    )

    monkeypatch.setattr(
        "ingestion.layout_filter.extract_text_blocks",
        lambda _path, max_pages=None: (blocks, 100),
    )

    policy = build_layout_filter_policy(tmp_path / "sample.pdf")

    assert watermark in policy.repeated_artifact_texts
    assert "3.1.2 description" not in policy.repeated_artifact_texts


def test_printed_page_number_requires_bottom_centre_geometry() -> None:
    printed_number = make_block(
        page_number=12,
        text="2",
        normalized_text="<n>",
        location="bottom",
        x0=295,
        y0=765,
        x1=310,
        y1=775,
    )
    body_number = make_block(
        page_number=12,
        text="2",
        normalized_text="<n>",
        location="body",
        x0=200,
        y0=300,
        x1=215,
        y1=315,
    )

    assert is_printed_page_number(printed_number)
    assert not is_printed_page_number(body_number)


def test_watermark_is_removed_even_when_misclassified_as_body() -> None:
    normalized = "complimentary member copy"
    policy = LayoutFilterPolicy(
        total_pages=100,
        analyzed_pages=100,
        repeated_artifact_texts=frozenset({normalized}),
    )
    block = make_block(
        page_number=1,
        text="Complimentary Member Copy",
        normalized_text=normalized,
        location="body",
    )

    assert removal_reason(block, policy) == "repeated_edge_artifact"


def test_legitimate_repeated_heading_is_preserved() -> None:
    policy = LayoutFilterPolicy(
        total_pages=100,
        analyzed_pages=100,
        repeated_artifact_texts=frozenset({"complimentary member copy"}),
    )
    heading = make_block(
        page_number=10,
        text="3.1.2 Description",
        normalized_text="3.1.2 description",
        location="body",
    )

    kept, stats, removed = filter_blocks([heading], policy)

    assert kept == [heading]
    assert stats.removed_blocks == 0
    assert removed == []


def test_policy_does_not_learn_repeated_content_in_small_document(
    monkeypatch,
    tmp_path: Path,
) -> None:
    normalized = "page <n> business analysis content."

    blocks = [
        make_block(
            page_number=page,
            text=f"Page {page} business analysis content.",
            normalized_text=normalized,
            location="top",
            x0=72,
            y0=60,
            x1=250,
            y1=75,
        )
        for page in range(1, 4)
    ]

    monkeypatch.setattr(
        "ingestion.layout_filter.extract_text_blocks",
        lambda _path, max_pages=None: (blocks, 3),
    )

    policy = build_layout_filter_policy(tmp_path / "sample.pdf")

    assert normalized not in policy.repeated_artifact_texts
