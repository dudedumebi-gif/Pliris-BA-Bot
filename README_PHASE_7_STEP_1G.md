# Phase 7 Step 1G — Clarification Continuation

Scope clarification is now a real session-owned conversation turn.

Before this increment, the API returned clarification before issuing a
conversation token or persisting the exchange. The next user reply therefore
had no prior clarification context.

This increment:

- issues a signed conversation token before returning clarification;
- persists the ambiguous user turn and Pliris clarification;
- allows the existing bounded history reader and context resolver to resolve
  the next user reply;
- avoids retrieval and grounded generation for the clarification turn itself;
- preserves anonymous session isolation.
