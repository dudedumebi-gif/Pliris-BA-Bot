import pytest

from app.health_view import (
    check_label,
    configuration_rows,
    format_checked_at,
    format_latency,
    status_label,
)


def test_health_view_formats_controlled_checks_and_statuses() -> None:
    assert check_label("api_process") == "API process"
    assert check_label("supabase_data_api") == "Supabase Data API"
    assert status_label("healthy") == "Healthy"
    assert status_label("unavailable") == "Unavailable"
    with pytest.raises(ValueError):
        check_label("secret_store")
    with pytest.raises(ValueError):
        status_label("unknown")


def test_health_view_formats_probe_latency_and_timestamp() -> None:
    assert format_latency(0.2) == "<1 ms"
    assert format_latency(425) == "425 ms"
    assert format_latency(1250.5) == "1.25 s"
    assert format_checked_at("2026-08-12T08:30:00+00:00") == ("2026-08-12 08:30 UTC")
    assert format_checked_at("not-a-date") == "at an unknown time"


def test_health_view_preserves_safe_configuration_order() -> None:
    rows = configuration_rows(
        {
            "app_name": "Pliris BA Bot",
            "app_env": "test",
            "chat_model": "gpt-test",
            "embedding_model": "embedding-test",
            "embedding_dimensions": 1536,
            "storage_bucket": "knowledge-base",
            "monitoring_enabled": True,
            "feedback_enabled": True,
        }
    )

    assert rows[0] == {"Setting": "Application", "Value": "Pliris BA Bot"}
    assert rows[-1] == {"Setting": "Feedback enabled", "Value": True}
    assert len(rows) == 8
