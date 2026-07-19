from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluation.llm_human_review import (
    RESPONSE_FAILURE_NOTE,
    RESPONSE_FAILURE_TEXT,
    HumanReviewError,
    _review_set_fingerprint,
    build_blind_assignments,
    validate_human_scores,
)


def _contract():
    cases = (SimpleNamespace(id="case_1"), SimpleNamespace(id="case_2"))
    benchmark = SimpleNamespace(cases=cases)
    config = SimpleNamespace(
        variant_ids=("baseline", "evidence", "decision"),
        primary_repetitions=1,
    )
    return SimpleNamespace(benchmark=benchmark, config=config)


def _records():
    rows = {}
    for case_id in ("case_1", "case_2"):
        for variant_id in ("baseline", "evidence", "decision"):
            rows[f"{case_id}::{variant_id}::r1"] = SimpleNamespace(status="success")
    return rows


def test_blind_assignments_are_deterministic(monkeypatch) -> None:
    monkeypatch.setattr(
        "evaluation.llm_human_review.contract_fingerprint",
        lambda _: "a" * 64,
    )
    first = build_blind_assignments(_contract(), _records())
    second = build_blind_assignments(_contract(), _records())
    assert first == second


def test_every_case_has_a_b_c_labels(monkeypatch) -> None:
    monkeypatch.setattr(
        "evaluation.llm_human_review.contract_fingerprint",
        lambda _: "a" * 64,
    )
    assignments = build_blind_assignments(_contract(), _records())
    for case_id in ("case_1", "case_2"):
        assert {item.response_label for item in assignments if item.case_id == case_id} == {
            "Answer A",
            "Answer B",
            "Answer C",
        }


def test_failure_assignment_is_explicit(monkeypatch) -> None:
    monkeypatch.setattr(
        "evaluation.llm_human_review.contract_fingerprint",
        lambda _: "a" * 64,
    )
    records = _records()
    records["case_1::baseline::r1"] = SimpleNamespace(status="error")
    assignments = build_blind_assignments(_contract(), records)
    assert any(item.response_status == "contract_failure" for item in assignments)


def test_failure_placeholder_is_stable() -> None:
    assert "RESPONSE UNAVAILABLE" in RESPONSE_FAILURE_TEXT
    assert "citation contract" in RESPONSE_FAILURE_NOTE


def _write_review_and_scores(tmp_path: Path):
    review_path = tmp_path / "review.csv"
    scores_path = tmp_path / "scores.csv"
    review_rows = [
        {
            "review_set_fingerprint": "",
            "review_id": "review-0000000001",
            "case_id": "case_1",
            "response_label": "Answer A",
            "response_status": "accepted",
            "response_text": "Supported [S1].",
        },
        {
            "review_set_fingerprint": "",
            "review_id": "review-0000000002",
            "case_id": "case_1",
            "response_label": "Answer B",
            "response_status": "contract_failure",
            "response_text": RESPONSE_FAILURE_TEXT,
        },
    ]
    fingerprint = _review_set_fingerprint(review_rows)
    for row in review_rows:
        row["review_set_fingerprint"] = fingerprint
    review_fields = list(review_rows[0])
    with review_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=review_fields)
        writer.writeheader()
        writer.writerows(review_rows)

    score_rows = [
        {
            "review_set_fingerprint": fingerprint,
            "review_id": "review-0000000001",
            "case_id": "case_1",
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
            "case_id": "case_1",
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
    score_fields = list(score_rows[0])
    with scores_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=score_fields)
        writer.writeheader()
        writer.writerows(score_rows)

    key = SimpleNamespace(
        review_set_fingerprint=fingerprint,
        attempt_count=2,
    )
    return review_path, scores_path, key


def test_validate_complete_scores(tmp_path: Path) -> None:
    review, scores, key = _write_review_and_scores(tmp_path)
    validated = validate_human_scores(scores, review, key)
    assert len(validated) == 2


def test_reject_missing_score_row(tmp_path: Path) -> None:
    review, scores, key = _write_review_and_scores(tmp_path)
    rows = list(csv.DictReader(scores.open("r", encoding="utf-8-sig")))[:1]
    with scores.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(HumanReviewError, match="exactly 2 rows"):
        validate_human_scores(scores, review, key)


def test_reject_out_of_range_score(tmp_path: Path) -> None:
    review, scores, key = _write_review_and_scores(tmp_path)
    rows = list(csv.DictReader(scores.open("r", encoding="utf-8-sig")))
    rows[0]["groundedness"] = "5"
    with scores.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(HumanReviewError, match="whole number"):
        validate_human_scores(scores, review, key)


def test_reject_fractional_score(tmp_path: Path) -> None:
    review, scores, key = _write_review_and_scores(tmp_path)
    rows = list(csv.DictReader(scores.open("r", encoding="utf-8-sig")))
    rows[0]["groundedness"] = "3.5"
    with scores.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(HumanReviewError, match="whole number"):
        validate_human_scores(scores, review, key)


def test_reject_blank_score(tmp_path: Path) -> None:
    review, scores, key = _write_review_and_scores(tmp_path)
    rows = list(csv.DictReader(scores.open("r", encoding="utf-8-sig")))
    rows[0]["groundedness"] = ""
    with scores.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(HumanReviewError, match="Missing groundedness"):
        validate_human_scores(scores, review, key)


def test_contract_failure_scores_locked(tmp_path: Path) -> None:
    review, scores, key = _write_review_and_scores(tmp_path)
    rows = list(csv.DictReader(scores.open("r", encoding="utf-8-sig")))
    rows[1]["groundedness"] = "1"
    with scores.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(HumanReviewError, match="must remain scored 0"):
        validate_human_scores(scores, review, key)


def test_contract_failure_note_locked(tmp_path: Path) -> None:
    review, scores, key = _write_review_and_scores(tmp_path)
    rows = list(csv.DictReader(scores.open("r", encoding="utf-8-sig")))
    rows[1]["reviewer_notes"] = "changed"
    with scores.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(HumanReviewError, match="note must remain unchanged"):
        validate_human_scores(scores, review, key)


def test_critical_accepted_requires_note(tmp_path: Path) -> None:
    review, scores, key = _write_review_and_scores(tmp_path)
    rows = list(csv.DictReader(scores.open("r", encoding="utf-8-sig")))
    rows[0]["critical_failure"] = "true"
    with scores.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(HumanReviewError, match="require a reviewer note"):
        validate_human_scores(scores, review, key)


def test_reject_tampered_review(tmp_path: Path) -> None:
    review, scores, key = _write_review_and_scores(tmp_path)
    rows = list(csv.DictReader(review.open("r", encoding="utf-8-sig")))
    rows[0]["response_text"] = "tampered"
    with review.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(HumanReviewError, match="fingerprint validation"):
        validate_human_scores(scores, review, key)


def test_reject_duplicate_score_id(tmp_path: Path) -> None:
    review, scores, key = _write_review_and_scores(tmp_path)
    rows = list(csv.DictReader(scores.open("r", encoding="utf-8-sig")))
    rows[1]["review_id"] = rows[0]["review_id"]
    with scores.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(HumanReviewError, match="must be unique"):
        validate_human_scores(scores, review, key)


def test_reject_identity_mismatch(tmp_path: Path) -> None:
    review, scores, key = _write_review_and_scores(tmp_path)
    rows = list(csv.DictReader(scores.open("r", encoding="utf-8-sig")))
    rows[0]["response_label"] = "Answer C"
    with scores.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(HumanReviewError, match="response_label mismatch"):
        validate_human_scores(scores, review, key)


def test_reject_invalid_boolean(tmp_path: Path) -> None:
    review, scores, key = _write_review_and_scores(tmp_path)
    rows = list(csv.DictReader(scores.open("r", encoding="utf-8-sig")))
    rows[0]["critical_failure"] = "yes"
    with scores.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(HumanReviewError, match="true or false"):
        validate_human_scores(scores, review, key)


def test_review_fingerprint_ignores_embedded_fingerprint() -> None:
    rows = [{"review_set_fingerprint": "x", "review_id": "one"}]
    first = _review_set_fingerprint(rows)
    rows[0]["review_set_fingerprint"] = "y"
    second = _review_set_fingerprint(rows)
    assert first == second


def test_labels_hide_variant_names(monkeypatch) -> None:
    monkeypatch.setattr(
        "evaluation.llm_human_review.contract_fingerprint",
        lambda _: "a" * 64,
    )
    assignments = build_blind_assignments(_contract(), _records())
    assert all(item.response_label.startswith("Answer ") for item in assignments)


def test_assignments_cover_all_attempts(monkeypatch) -> None:
    monkeypatch.setattr(
        "evaluation.llm_human_review.contract_fingerprint",
        lambda _: "a" * 64,
    )
    assignments = build_blind_assignments(_contract(), _records())
    assert len(assignments) == 6
