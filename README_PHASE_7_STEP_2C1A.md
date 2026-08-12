# Phase 7 Step 2C1A - Lifecycle and Audit Backend

This increment establishes guarded archive/restore operations before any
developer UI mutation, upload, storage removal, or paid ingestion control.

Included:

- append-only `source_admin_events`;
- atomic document status update plus audit insertion;
- exact manifest-ID confirmation;
- archive only from `ready`;
- restore only from `archived`;
- restore readiness check requiring every retained chunk to be embedded;
- protected lifecycle API routes;
- regression coverage proving `hybrid_search` excludes non-ready sources.

BABOK must remain untouched. The permanent GAO Agile Assessment Guide is the
lifecycle acceptance source.
