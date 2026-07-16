from __future__ import annotations

from pathlib import Path

import yaml

from ingestion.models import CorpusManifest, DocumentManifestEntry
from pliris.config.settings import get_settings


def load_manifest(path: Path | None = None) -> CorpusManifest:
    """Load and validate the corpus manifest."""
    settings = get_settings()
    manifest_path = path or settings.corpus_manifest_path

    if not manifest_path.exists():
        raise FileNotFoundError(f"Corpus manifest not found: {manifest_path}")

    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("The corpus manifest must contain a YAML mapping.")

    return CorpusManifest.model_validate(raw)


def get_manifest_document(
    document_id: str,
    path: Path | None = None,
) -> DocumentManifestEntry:
    """Return one enabled manifest document by stable document ID."""
    manifest = load_manifest(path)

    for document in manifest.documents:
        if document.document_id == document_id:
            if not document.enabled:
                raise ValueError(f"Document is disabled in the manifest: {document_id}")
            return document

    raise KeyError(f"Document ID not found in corpus manifest: {document_id}")


def resolve_source_path(
    document: DocumentManifestEntry,
    private_directory: Path | None = None,
) -> Path:
    """Resolve a manifest filename safely inside the configured private directory."""
    settings = get_settings()
    base_directory = (private_directory or settings.private_document_directory).resolve()
    source_path = (base_directory / document.source_filename).resolve()

    if base_directory not in source_path.parents:
        raise ValueError("Manifest source filename resolves outside data/private.")

    if not source_path.exists():
        raise FileNotFoundError(
            f"Source PDF not found: {source_path}. "
            "Confirm the filename matches data/corpus_manifest.yaml."
        )

    if source_path.suffix.lower() != ".pdf":
        raise ValueError(f"Only PDF sources are supported in Phase 2: {source_path}")

    return source_path
