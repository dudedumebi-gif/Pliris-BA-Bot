# Phase 7 Step 2C1B - Lifecycle Developer-Interface Integration

This increment connects the protected source workspace to the guarded lifecycle
backend added in Step 2C1A.

Included:

- archive controls for `ready` sources and restore controls for `archived` sources;
- permanent UI protection for BABOK (`babok-v3`);
- exact manifest-ID confirmation and a 10–500 character audit reason;
- safe client handling for validation, conflict, authorization, timeout, and server failures;
- recent append-only lifecycle events;
- post-transition refresh of source details, metrics, and audit history;
- GAO (`gao-agile-assessment-guide-2023`) as the lifecycle acceptance source.

Archive remains reversible and retains indexed chunks while excluding the source
from retrieval. Restore requires every retained chunk to remain embedded.

Upload, ingestion, re-ingestion, deletion, storage removal, migration execution,
and paid-provider calls remain outside this increment.
