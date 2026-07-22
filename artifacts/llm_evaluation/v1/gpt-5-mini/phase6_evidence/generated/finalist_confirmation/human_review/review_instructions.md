# Pliris Phase 6 Step 4B — Blinded Finalist Diagnostic Review

Do not open `blinding_key.json` until finalization succeeds.

Review every row in `blinded_responses.csv`, then enter whole-number scores
from 0 through 4 in `scores.csv`.

Scale: 0 unusable; 1 major deficiencies; 2 partial; 3 solid; 4 excellent.

Dimensions:
- groundedness
- citation_quality
- mode_fulfillment
- completeness
- relevance_clarity
- uncertainty_handling

Set `critical_failure` to `true` only for an unusable response and add a
concise note. Contract-failure rows are locked to zero scores, `true`, and
the generated note; do not change them.

This is diagnostic review. Human scores cannot override a failed automated
gate and cannot select a production prompt.

Review-set fingerprint:

`e3f44316b3643ef36084b8a60baa39019935f423db5b6aae5383aed0fe96b703`
