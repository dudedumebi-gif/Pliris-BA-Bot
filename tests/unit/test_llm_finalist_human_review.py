from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluation.llm_finalist_human_review import (
    RESPONSE_FAILURE_NOTE,
    FinalistHumanReviewError,
    _ordered_variant_ids,
    _review_set_fingerprint,
    validate_scores,
)


def test_blind_order_is_deterministic() -> None:
    first = _ordered_variant_ids("a" * 64, "case", ("baseline", "hardened"))
    second = _ordered_variant_ids("a" * 64, "case", ("baseline", "hardened"))
    assert first == second
    assert set(first) == {"baseline", "hardened"}


def test_review_fingerprint_ignores_embedded_value() -> None:
    rows = [{"review_set_fingerprint": "x", "review_id": "one"}]
    first = _review_set_fingerprint(rows)
    rows[0]["review_set_fingerprint"] = "y"
    assert _review_set_fingerprint(rows) == first


def _files(tmp_path: Path):
    review = tmp_path / "review.csv"
    scores = tmp_path / "scores.csv"
    rows = [
        {
            "review_set_fingerprint": "",
            "review_id": "review-0000000001",
            "case_id": "case",
            "response_label": "Answer A",
            "response_status": "accepted",
            "response_text": "Supported [S1].",
        },
        {
            "review_set_fingerprint": "",
            "review_id": "review-0000000002",
            "case_id": "case",
            "response_label": "Answer B",
            "response_status": "contract_failure",
            "response_text": "unavailable",
        },
    ]
    fingerprint = _review_set_fingerprint(rows)
    for row in rows:
        row["review_set_fingerprint"] = fingerprint
    with review.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    score_rows = [
        {
            "review_set_fingerprint": fingerprint,
            "review_id": "review-0000000001",
            "case_id": "case",
            "response_label": "Answer A",
            "response_status": "accepted",
            "groundedness": "4",
            "citation_quality": "4",
            "mode_fulfillment": "4",
            "completeness": "4",
            "relevance_clarity": "4",
            "uncertainty_handling": "4",
            "critical_failure": "false",
            "reviewer_notes": "",
        },
        {
            "review_set_fingerprint": fingerprint,
            "review_id": "review-0000000002",
            "case_id": "case",
            "response_label": "Answer B",
            "response_status": "contract_failure",
            "groundedness": "0",
            "citation_quality": "0",
            "mode_fulfillment": "0",
            "completeness": "0",
            "relevance_clarity": "0",
            "uncertainty_handling": "0",
            "critical_failure": "true",
            "reviewer_notes": RESPONSE_FAILURE_NOTE,
        },
    ]
    with scores.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(score_rows[0]))
        writer.writeheader()
        writer.writerows(score_rows)
    key = SimpleNamespace(review_set_fingerprint=fingerprint, attempt_count=2)
    return review, scores, key


def _rewrite(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_valid_scores_pass(tmp_path: Path) -> None:
    review, scores, key = _files(tmp_path)
    assert len(validate_scores(scores, review, key)) == 2


def test_missing_row_rejected(tmp_path: Path) -> None:
    review, scores, key = _files(tmp_path)
    rows = list(csv.DictReader(scores.open("r", encoding="utf-8-sig")))[:1]
    _rewrite(scores, rows)
    with pytest.raises(FinalistHumanReviewError, match="incomplete"):
        validate_scores(scores, review, key)


def test_fractional_score_rejected(tmp_path: Path) -> None:
    review, scores, key = _files(tmp_path)
    rows = list(csv.DictReader(scores.open("r", encoding="utf-8-sig")))
    rows[0]["groundedness"] = "3.5"
    _rewrite(scores, rows)
    with pytest.raises(FinalistHumanReviewError, match="whole number"):
        validate_scores(scores, review, key)


def test_failure_score_locked(tmp_path: Path) -> None:
    review, scores, key = _files(tmp_path)
    rows = list(csv.DictReader(scores.open("r", encoding="utf-8-sig")))
    rows[1]["groundedness"] = "1"
    _rewrite(scores, rows)
    with pytest.raises(FinalistHumanReviewError, match="not locked"):
        validate_scores(scores, review, key)


def test_failure_note_locked(tmp_path: Path) -> None:
    review, scores, key = _files(tmp_path)
    rows = list(csv.DictReader(scores.open("r", encoding="utf-8-sig")))
    rows[1]["reviewer_notes"] = "changed"
    _rewrite(scores, rows)
    with pytest.raises(FinalistHumanReviewError, match="not locked"):
        validate_scores(scores, review, key)


def test_critical_accepted_requires_note(tmp_path: Path) -> None:
    review, scores, key = _files(tmp_path)
    rows = list(csv.DictReader(scores.open("r", encoding="utf-8-sig")))
    rows[0]["critical_failure"] = "true"
    _rewrite(scores, rows)
    with pytest.raises(FinalistHumanReviewError, match="requires a reviewer note"):
        validate_scores(scores, review, key)


def test_tampered_review_rejected(tmp_path: Path) -> None:
    review, scores, key = _files(tmp_path)
    rows = list(csv.DictReader(review.open("r", encoding="utf-8-sig")))
    rows[0]["response_text"] = "tampered"
    _rewrite(review, rows)
    with pytest.raises(FinalistHumanReviewError, match="fingerprint"):
        validate_scores(scores, review, key)


def test_identity_mismatch_rejected(tmp_path: Path) -> None:
    review, scores, key = _files(tmp_path)
    rows = list(csv.DictReader(scores.open("r", encoding="utf-8-sig")))
    rows[0]["response_label"] = "Answer B"
    _rewrite(scores, rows)
    with pytest.raises(FinalistHumanReviewError, match="response_label mismatch"):
        validate_scores(scores, review, key)
