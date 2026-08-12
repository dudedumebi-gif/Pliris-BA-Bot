# Phase 8 submission audit

This criterion-by-criterion index identifies the review evidence for the release candidate. Dynamic
checks remain provisional until the draft pull request completes remote CI and security scanning.

| Criterion | Evidence | Gate |
|---|---|---|
| Complete packaging | `Dockerfile`, `docker-compose.yml`, `.dockerignore` | Compose config, build, smoke test |
| Reproducible dependencies | exact direct constraints, `uv.lock`, uv 0.11.30 | `uv sync --frozen` |
| Public corpus | `data/sample/`, manifest entry, build script | extraction unit test |
| Setup and usage | README, setup, usage, ingestion docs | clean-machine walkthrough |
| Product demonstration | `docs/walkthrough.md`, three acceptance screenshots | manual review |
| Offline quality | Ruff format/lint and non-integration tests | CI workflow |
| Dependency/system CVEs | Trivy filesystem and final-image reports | no unaccepted fixable High/Critical |
| Python security | CodeQL `security-extended` | no unresolved release-blocking alert |
| Auditability | JSON, SARIF, CycloneDX SBOM, SHA/image summary | retained workflow artifacts |
| Privacy | `.gitignore`, `.dockerignore`, bounded diagnostics | secret scan and manual review |
| Retrieval/generation quality | `docs/evaluation.md`, evaluation datasets and evidence tooling | documented quality gates |
| Operations | health/readiness, monitoring, feedback | automated tests and screenshots |

## Finalization checklist

- [ ] Offline CI passes on the exact release-candidate SHA.
- [ ] CodeQL passes and all alerts are reviewed.
- [ ] Trivy filesystem and image gates pass.
- [ ] Security artifact identities match the release-candidate SHA and image.
- [ ] Clean-machine Compose build, startup, health, and shutdown are verified.
- [ ] Public and developer interface walkthrough is reviewed.
- [ ] Draft PR is reviewed, marked ready, and merged with an approved merge commit.
- [ ] The resulting `main` commit is tagged only after every prior item passes.
