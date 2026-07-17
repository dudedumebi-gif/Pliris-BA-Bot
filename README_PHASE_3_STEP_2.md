# Phase 3 Step 2 - Conservative Layout Filtering

The audit showed two near-universal artifacts:

- the vertical member-copy watermark;
- printed page numbers in the bottom centre.

Repeated headings such as `Purpose`, `Description`, `Glossary`, and
`Techniques to Task Mapping` are deliberately preserved.

## Files

```text
ingestion/layout_filter.py
ingestion/pdf_extractor.py
scripts/compare_babok_extraction.py
tests/unit/test_layout_filter.py
README_PHASE_3_STEP_2.md
```

`ingestion/pdf_extractor.py` replaces the Phase 2 version.

## Why the filter is conservative

A repeated text phrase is learned as removable only when:

- it appears on at least 80% of analyzed pages;
- at least 80% of its occurrences are near a page edge;
- it is not numeric-only;
- it has enough text to avoid deleting labels or diagram values.

Printed page numbers use separate geometry:

- numeric-only;
- bottom region;
- near the horizontal centre;
- small block dimensions.

No global replacements of words such as `Distribution`, `Management`,
`Definition`, or `Glossary` are used.

## Merge and check

Copy the package into the repository root, then run:

```bash
uv run ruff format .
uv run ruff check .
uv run pytest tests/unit/test_layout_audit.py \
  tests/unit/test_layout_filter.py -v
```

Run all unit tests:

```bash
uv run pytest -m "not integration" -q
```

## Compare representative BABOK pages

```bash
uv run python -m scripts.compare_babok_extraction \
  --document-id babok-v3
```

Expected general result:

- one learned repeated artifact pattern;
- one watermark removed from nearly every selected content page;
- one printed page number removed from nearly every selected content page;
- legitimate section headings remain in cleaned text.

Generated outputs remain under the ignored directory:

```text
artifacts/layout_audit/
```

## Run full dry extraction

```bash
uv run python -m scripts.ingest_document \
  --document-id babok-v3 \
  --dry-run
```

The warnings should report roughly:

```text
Layout filter learned 1 repeated artifact pattern(s).
Layout filter removed 508 recurring edge block(s) and 501 printed page number(s).
```

Counts can differ slightly if the PDF version differs.

## Do not re-embed yet

Share the extraction comparison report and full dry-run output first.
Only then run a single forced reingestion.
