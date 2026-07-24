# Phase 7 Step 2A — Protected Read-Only Source API

This increment establishes the developer-only source inspection foundation.

Included: API-side developer-key enforcement, real PostgreSQL reads from
`public.documents` and `public.document_chunks`, bounded list/search/status
filters, aggregate statistics, safe source detail, paginated chunk inspection,
router registration, and offline tests.

Uploads, downloads, ingestion triggers, archive/restore, and deletion remain
disabled until later Step 2 increments add validation and auditability.
