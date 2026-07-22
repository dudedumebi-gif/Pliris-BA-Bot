# Pliris Phase 6 LLM Evaluation Evidence

This directory is the deliberate, self-contained evidence set for Phase 6.

## Final decision

- Decision: `no_finalist_selected`
- Retained production prompt: `production_baseline_v1`
- Production prompt changed: `False`
- Human review may override a failed automated gate: `False`

The retained baseline is a no-change safety decision. It did not pass the frozen
combined acceptance policy.

## Frozen evidence totals

- Frozen contexts: `12`
- Primary attempts: `36`
- Primary contract failures: `6`
- Finalist attempts: `24`
- Finalist contract failures: `3`
- Total generation API calls: `55`
- Estimated total evaluation cost: `$0.17483089`

## Contents

- `contracts/` — copied frozen JSON contracts.
- `reproducibility/` — copied tracked workflow code and phase instructions.
- `generated/` — copied source-of-truth first-run outputs and review evidence.
- `commands.md` — documented reproduction sequence.
- `verification.json` — reported local quality gates plus derived evidence checks.
- `manifest.json` — file inventory, hashes, fingerprints, source commit, and decision.
- `checksums.sha256` — package integrity hashes.

Package fingerprint:

`10b6bbfff3ceb41e6c07a8e47fbe16b6144af0475eae80fb9f14baa03052d7be`
