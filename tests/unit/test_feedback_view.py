from app.feedback_view import (
    boolean_label,
    feedback_excerpt,
    feedback_label,
    format_percentage,
    format_timestamp,
)


def test_feedback_view_formats_rates_and_timestamps() -> None:
    assert format_percentage(3, 4) == "75.0%"
    assert format_percentage(0, 0) == "—"
    assert format_timestamp("2026-08-05T10:30:00+00:00") == "2026-08-05 10:30 UTC"
    assert format_timestamp("not-a-date") == "Not recorded"


def test_feedback_view_builds_safe_compact_labels() -> None:
    assert feedback_excerpt("  A   useful response.  ") == "A useful response."
    assert feedback_excerpt("x" * 200, limit=20).endswith("…")
    assert feedback_label({"rating": 1, "assistant_message": "Answer"}) == ("Helpful · Answer")
    assert boolean_label(True) == "Yes"
    assert boolean_label(False) == "No"
    assert boolean_label(None) == "Not rated"
