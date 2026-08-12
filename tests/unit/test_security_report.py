from collections import Counter

from scripts.security_report import build_markdown, summarize


def test_summarize_counts_and_selects_only_fixable_high_critical() -> None:
    report = {
        "Results": [
            {
                "Vulnerabilities": [
                    {"Severity": "LOW", "FixedVersion": "2"},
                    {"Severity": "HIGH", "FixedVersion": ""},
                    {"Severity": "HIGH", "FixedVersion": "3", "VulnerabilityID": "CVE-1"},
                    {"Severity": "CRITICAL", "FixedVersion": "4", "VulnerabilityID": "CVE-2"},
                ]
            }
        ]
    }

    totals, blocking = summarize(report)

    assert totals == Counter({"HIGH": 2, "LOW": 1, "CRITICAL": 1})
    assert [item["VulnerabilityID"] for item in blocking] == ["CVE-1", "CVE-2"]


def test_build_markdown_records_release_identity_and_pass() -> None:
    markdown = build_markdown(
        commit="abc123",
        image_ref="pliris:abc123",
        image_id="sha256:123",
        trivy_version="Version: 0.72.0",
        filesystem=(Counter(), []),
        image=(Counter({"LOW": 1}), []),
    )

    assert "`abc123`" in markdown
    assert "`sha256:123`" in markdown
    assert "**PASS**" in markdown
    assert "No fixable High or Critical" in markdown
