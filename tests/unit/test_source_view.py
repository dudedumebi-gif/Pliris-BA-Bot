import pytest

from app.source_view import (
    LIFECYCLE_ACCEPTANCE_MANIFEST_ID,
    STAGING_ACCEPTANCE_MANIFEST_ID,
    chunk_page_count,
    format_count,
    format_timestamp,
    lifecycle_action_for_source,
    lifecycle_event_label,
    page_range_label,
    source_option_label,
    staging_filename_for_manifest,
    validate_lifecycle_input,
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
    rendered = format_timestamp("2026-07-23T22:00:00+00:00")
    assert rendered != "Not available"
    assert "2026" in rendered


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


def test_lifecycle_action_protects_babok_and_respects_status() -> None:
    assert lifecycle_action_for_source({"manifest_id": "babok-v3", "status": "ready"}) is None
    assert (
        lifecycle_action_for_source(
            {
                "manifest_id": LIFECYCLE_ACCEPTANCE_MANIFEST_ID,
                "status": "ready",
            }
        )
        == "archive"
    )
    assert (
        lifecycle_action_for_source(
            {
                "manifest_id": LIFECYCLE_ACCEPTANCE_MANIFEST_ID,
                "status": "archived",
            }
        )
        == "restore"
    )
    assert lifecycle_action_for_source({"manifest_id": "other", "status": "failed"}) is None


def test_lifecycle_input_requires_reason_and_exact_manifest_confirmation() -> None:
    manifest_id = LIFECYCLE_ACCEPTANCE_MANIFEST_ID
    assert (
        validate_lifecycle_input(
            reason="Too short",
            confirmation=manifest_id,
            manifest_id=manifest_id,
        )
        == "Provide a reason between 10 and 500 characters."
    )
    assert (
        validate_lifecycle_input(
            reason="Valid lifecycle reason.",
            confirmation=manifest_id.upper(),
            manifest_id=manifest_id,
        )
        == "Enter the exact, case-sensitive manifest ID shown above."
    )
    assert (
        validate_lifecycle_input(
            reason="Valid lifecycle reason.",
            confirmation=manifest_id,
            manifest_id=manifest_id,
        )
        is None
    )


def test_lifecycle_event_label_is_safe_and_informative() -> None:
    label = lifecycle_event_label(
        {
            "action": "archive",
            "previous_status": "ready",
            "new_status": "archived",
            "created_at": "2026-07-24T12:00:00+00:00",
        }
    )
    assert label.startswith("Archive · ready → archived · 2026-07-24")


def test_staging_target_allows_only_controlled_gao_source() -> None:
    assert (
        staging_filename_for_manifest(STAGING_ACCEPTANCE_MANIFEST_ID)
        == "GAO_Agile_Assessment_Guide_2023.pdf"
    )
    assert staging_filename_for_manifest("babok-v3") is None
    assert staging_filename_for_manifest("unapproved-source") is None
