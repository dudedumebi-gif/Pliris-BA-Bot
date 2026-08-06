import pytest

from app.monitoring_view import (
    format_count,
    format_generated_at,
    format_latency,
    format_percentage,
    window_hours,
)


def test_monitoring_view_maps_controlled_windows() -> None:
    assert window_hours("Last 24 hours") == 24
    assert window_hours("Last 7 days") == 168
    assert window_hours("Last 30 days") == 720
    with pytest.raises(ValueError):
        window_hours("All time")


def test_monitoring_view_formats_counts_and_latency() -> None:
    assert format_count(1200) == "1,200"
    assert format_latency(None) == "—"
    assert format_latency(425) == "425 ms"
    assert format_latency(1250.5) == "1.25 s"
    assert format_latency(90_000) == "1.5 min"


def test_monitoring_view_formats_rates_without_inventing_empty_samples() -> None:
    assert format_percentage(3, 4) == "75.0%"
    assert format_percentage(0, 0) == "—"
    assert format_percentage(7, 4) == "100.0%"


def test_monitoring_view_formats_generated_timestamp() -> None:
    assert format_generated_at("2026-08-06T08:30:00+00:00") == ("2026-08-06 08:30 UTC")
    assert format_generated_at("not-a-date") == "at an unknown time"
