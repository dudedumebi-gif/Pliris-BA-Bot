# Phase 1 Deliverables and Development Gate

## Codebase assimilation decision

### Retain and adapt

- OpenAI Responses API interaction pattern.
- Separation of retrieval, context construction, and LLM generation.
- Structured-output and retry utilities.
- Hit Rate, MRR, and LLM-as-a-judge evaluation concepts.
- Token, latency, cost, feedback, and dashboard concepts.
- Deterministic orchestration before autonomous agent behaviour.

### Replace

- DataTalks.Club FAQ corpus.
- MinSearch as the production knowledge base.
- Local PostgreSQL containers for application data.
- Recreating indexes whenever the assistant starts.
- Database initialization code that drops tables.
- Direct Streamlit access to secrets, the LLM, or database.
- Course-specific `question`, `answer`, `section`, and `course` schemas.

### Defer

- Kestra as a required runtime dependency.
- Multi-agent architecture.
- Web search.
- Grafana.

These can be added only after the core RAG path is measured and stable.

## Delivery sequence

### Gate 1 — Environment and Supabase

Deliver:

- Validated settings.
- Admin Supabase client.
- Session Pooler connection pool.
- Hosted integration script.
- Health endpoints.
- Unit and integration tests.
- Locked dependencies.

Exit criteria:

- Every integration check passes.
- No secret leakage.
- Temporary test records are cleaned up.

### Gate 2 — Ingestion vertical slice

Deliver:

- One PDF ingested end to end.
- Page-aware chunks in `document_chunks`.
- Embeddings in `vector(1536)`.
- Original PDF in the private Storage bucket.
- Idempotent rerun behaviour.
- Ingestion audit entry.
- Retrieval of a known passage.

### Gate 3 — Baseline domain RAG

Deliver:

- Scope classifier.
- Out-of-scope redirect.
- Hybrid retrieval.
- Context builder with page citations.
- Grounded BA response.
- Insufficient-evidence response.
- Conversation and retrieval telemetry.

### Gate 4 — Evaluation

Deliver:

- Ground-truth dataset.
- Lexical vs semantic vs hybrid comparison.
- Baseline vs structured vs query-aware prompt comparison.
- Scope-guardrail confusion matrix.
- Saved evaluation reports.

### Gate 5 — Interface and monitoring

Deliver:

- Streamlit chat interface calling FastAPI.
- User feedback.
- Source viewer.
- Monitoring dashboard with at least five charts.

### Gate 6 — Containers and reproducibility

Deliver:

- FastAPI and Streamlit in Docker Compose.
- Hosted Supabase remains external.
- Complete setup and usage documentation.
- Sample/public corpus.
- Clean-clone reproducibility test.
