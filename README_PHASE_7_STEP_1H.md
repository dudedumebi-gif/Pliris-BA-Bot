# Phase 7 Step 1H — Deterministic Clarification Resolution

Step 1G persisted clarification turns, but the context resolver still depended
on a finite phrase list. Replies such as `I'm talking about a financial
business analyst` were treated as standalone queries, allowing different
scope outcomes.

This increment makes clarification continuation state-based:

- clarification assistant messages carry an internal turn marker;
- bounded history preserves that marker;
- the next user reply is always combined with the original ambiguous question;
- scope, retrieval, and generation receive the same composite query for the
  same conversation state;
- ordinary standalone messages and explicit follow-ups remain unchanged.

No organization-specific role titles are hard-coded.

## Monitoring-safe clarification state

Clarification state is carried by the existing `messages.scope_status='borderline'` field. It is not written to `model_name`, so model usage and EvalOps analytics remain accurate.
