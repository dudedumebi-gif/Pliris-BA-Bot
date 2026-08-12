# Phase 7 Step 2C1C - Guarded PDF Staging and Ingestion

This increment connects the protected developer Sources workspace to a guarded
PDF staging and ingestion workflow after the lifecycle controls added in Steps
2C1A and 2C1B.

Included:

- manifest-backed PDF upload validation;
- private storage with duplicate-checksum rejection;
- creation of non-retrievable `pending` document records;
- exact staged handoff checks for document UUID, manifest ID, checksum, storage
  location, status, and absence of existing chunks;
- dry-run inspection without storage, database writes, or embeddings;
- rejection of `--force` when `--staged-document-id` is supplied;
- persistence of successfully indexed documents with status `ready`;
- API, client, interface, repository, storage, pipeline, and CLI regression
  coverage.

The controlled GAO Agile Assessment Guide acceptance processed 324 pages into
204 fully embedded chunks with no ingestion error. The persisted document status
was `ready`. BABOK (`babok-v3`) remained untouched.
