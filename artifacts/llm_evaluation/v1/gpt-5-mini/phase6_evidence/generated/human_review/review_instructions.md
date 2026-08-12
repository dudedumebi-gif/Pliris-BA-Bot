# Pliris Phase 6 Blinded Human Review

Do not open `blinding_key.json` until the score sheet has been completed and saved.

Review every row in `blinded_responses.csv`, then enter whole-number scores from 0 through 4 in `scores.csv`.

## Scale

- 0 — unusable, unsupported, or materially violates the review contract
- 1 — major deficiencies
- 2 — partially meets the criterion
- 3 — solid and substantially meets the criterion
- 4 — excellent and fully meets the criterion

## Dimensions

- **groundedness** (25%): Claims are supported by the supplied context and do not invent facts.
- **citation_quality** (20%): Inline citations are valid, sufficient, and close to the claims they support.
- **mode_fulfillment** (20%): The response follows the requested analysis or deliverable mode.
- **completeness** (15%): The response covers important supported aspects without fabricating missing details.
- **relevance_clarity** (10%): The response is direct, organized, and understandable.
- **uncertainty_handling** (10%): Assumptions, evidence gaps, unresolved conflicts, and conditional claims are handled appropriately.

## Critical failures

Set `critical_failure` to `true` for a response that is unusable because of fabrication, missing mandatory evidence, a materially wrong fallback, citation failure, or another severe contract violation. Add a concise note.

Rows marked `contract_failure` are intentionally pre-scored 0 across every dimension and marked as critical failures. Do not change those locked values.

The score sheet must contain all 36 rows. Step 3 does not select a production prompt.

Review-set fingerprint:

`a584db1c9c35aaaa628201c1cfe4e6c81c6308e1fd8252d1d94557db69dec0a0`
