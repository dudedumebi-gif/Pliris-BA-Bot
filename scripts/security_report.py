"""Create a human-readable release audit from Trivy JSON reports."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

BLOCKING_SEVERITIES = {"HIGH", "CRITICAL"}


def _vulnerabilities(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        vulnerability
        for result in report.get("Results") or []
        for vulnerability in result.get("Vulnerabilities") or []
    ]


def summarize(report: dict[str, Any]) -> tuple[Counter[str], list[dict[str, Any]]]:
    vulnerabilities = _vulnerabilities(report)
    totals = Counter(str(item.get("Severity", "UNKNOWN")).upper() for item in vulnerabilities)
    blocking = [
        item
        for item in vulnerabilities
        if str(item.get("Severity", "")).upper() in BLOCKING_SEVERITIES
        and bool(str(item.get("FixedVersion", "")).strip())
    ]
    return totals, blocking


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_optional(path: Path | None, fallback: str) -> str:
    if path is None or not path.exists():
        return fallback
    return path.read_text(encoding="utf-8").strip()


def _totals_row(name: str, totals: Counter[str], blocking: int) -> str:
    values = [totals.get(level, 0) for level in ("UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL")]
    return f"| {name} | {' | '.join(map(str, values))} | {blocking} |"


def build_markdown(
    *,
    commit: str,
    image_ref: str,
    image_id: str,
    trivy_version: str,
    filesystem: tuple[Counter[str], list[dict[str, Any]]],
    image: tuple[Counter[str], list[dict[str, Any]]],
) -> str:
    fs_totals, fs_blocking = filesystem
    image_totals, image_blocking = image
    blockers = [("filesystem", item) for item in fs_blocking] + [
        ("image", item) for item in image_blocking
    ]
    disposition = (
        "PASS" if not blockers else "FAIL — remediation or approved risk acceptance required"
    )
    lines = [
        "# Security audit",
        "",
        f"- Commit: `{commit}`",
        f"- Image: `{image_ref}`",
        f"- Image identity: `{image_id}`",
        f"- Scanner/database: `{trivy_version.replace(chr(10), '; ')}`",
        f"- Release-gate disposition: **{disposition}**",
        "",
        "## Vulnerability totals",
        "",
        "| Target | Unknown | Low | Medium | High | Critical | Fixable High/Critical |",
        "|---|---:|---:|---:|---:|---:|---:|",
        _totals_row("Repository/filesystem", fs_totals, len(fs_blocking)),
        _totals_row("Final image", image_totals, len(image_blocking)),
        "",
        "## Reproduction",
        "",
        "The pinned workflow `.github/workflows/security.yml` records the exact commands. It scans "
        "the repository for vulnerabilities, misconfiguration, and secrets; scans the built "
        "image for OS and language vulnerabilities; emits JSON and SARIF; and creates "
        "CycloneDX SBOMs.",
        "",
        "```bash",
        "trivy filesystem --include-dev-deps --scanners vuln,misconfig,secret .",
        f"docker build --tag {image_ref} .",
        f"trivy image --scanners vuln {image_ref}",
        "```",
        "",
        "## Blocking findings",
        "",
    ]
    if not blockers:
        lines.append("No fixable High or Critical vulnerability was reported.")
    else:
        lines.extend(
            f"- `{target}` `{item.get('VulnerabilityID', 'unknown')}` in "
            f"`{item.get('PkgName', 'unknown')}`: installed `{item.get('InstalledVersion', '?')}`, "
            f"fixed in `{item.get('FixedVersion', '?')}`"
            for target, item in blockers
        )
    lines.extend(
        [
            "",
            "Reports intentionally exclude credentials, raw environment values, and private "
            "corpus content.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--filesystem-report", required=True, type=Path)
    parser.add_argument("--image-report", required=True, type=Path)
    parser.add_argument("--commit", default="unknown")
    parser.add_argument("--image-ref", default="unknown")
    parser.add_argument("--image-id-file", type=Path)
    parser.add_argument("--trivy-version-file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on-fixable-high-critical", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    filesystem = summarize(_load(args.filesystem_report))
    image = summarize(_load(args.image_report))
    blockers = filesystem[1] + image[1]
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            build_markdown(
                commit=args.commit,
                image_ref=args.image_ref,
                image_id=_read_optional(args.image_id_file, "unknown"),
                trivy_version=_read_optional(args.trivy_version_file, "unknown"),
                filesystem=filesystem,
                image=image,
            ),
            encoding="utf-8",
        )
    if args.fail_on_fixable_high_critical and blockers:
        print(f"Release gate failed: {len(blockers)} fixable High/Critical finding(s).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
