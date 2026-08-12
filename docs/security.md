# Security and CVE audit

## Release gate

`.github/workflows/security.yml` runs on every pull request to `main` and on manual dispatch. It
uses immutable action SHAs, Trivy 0.73.0, and CodeQL 4.37.6.

| Coverage | Scanner | Evidence |
|---|---|---|
| Locked application dependencies | Trivy filesystem | JSON, SARIF, CycloneDX SBOM |
| IaC/configuration | Trivy misconfiguration | JSON and SARIF |
| Embedded secrets | Trivy secret scanner | JSON and SARIF |
| Final OS and Python packages | Trivy image | JSON, SARIF, CycloneDX SBOM |
| Python source and data flow | CodeQL `security-extended` | GitHub code-scanning results and SARIF artifact |

The final-image job builds the same `Dockerfile`, labels the image with the commit SHA, smoke-tests
its Streamlit health endpoint, records the immutable image ID, and then scans it. The workflow fails
when either target has a fixable High or Critical vulnerability.

The final scratch stage materializes the resolved runtime filesystem from the digest-pinned Python
stage. This preserves the complete Debian/Python runtime while preventing superseded base-layer
package metadata from being mistaken for installed packages.

System `pip`, `ensurepip`, and their bundled packages are removed. The image installs production
dependencies with the digest-pinned uv binary and `uv sync --frozen`; the removed Python packaging
tools are not application dependencies or runtime requirements.

## Evidence and retention

The `security-audit-<commit>` artifact contains the raw reports, both SBOMs, scanner/database
version, image identity, and `SECURITY_AUDIT.md`. The summary records severity totals and release
disposition. CodeQL SARIF is retained separately as `codeql-python-<commit>`. GitHub code scanning
also receives the SARIF results when repository settings permit uploads.

Artifacts never include `.env`, credentials, raw environment values, logs, or `data/private` because
those paths are excluded from the Docker build and repository. Review SARIF before sharing it
outside the project.

## Remediation and risk acceptance

Upgrade or replace the affected direct dependency or base image, regenerate `uv.lock`, rerun all
tests, and rerun the workflow. For transitive findings, prefer a compatible direct upgrade rather
than editing the lockfile manually.

An exception is allowed only when no safe fix is currently available. Record the CVE, affected
component/version, exploitability in this deployment, compensating controls, owner, approval,
expiry date (maximum 30 days), and tracking issue. A fixable High or Critical finding without that
time-bounded record blocks Phase 8.

## Local commands

With Trivy 0.73.0 and Docker installed, reproduce the core scans using the exact commands in the
workflow:

```bash
trivy filesystem --include-dev-deps --scanners vuln,misconfig,secret \
  --format json --output filesystem.json .
docker build --tag pliris-ba-bot:local .
trivy image --scanners vuln --format json --output image.json pliris-ba-bot:local
trivy image --scanners vuln --format cyclonedx --output image.cdx.json pliris-ba-bot:local
```

Do not commit generated reports; the workflow artifact ties them to the exact candidate commit and
image.
