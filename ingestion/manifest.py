"""Manage document manifest."""

import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

MANIFEST_PATH = Path("data/corpus_manifest.yaml")


def load_manifest() -> dict:
    """
    Load the document manifest.

    Returns:
        Manifest dictionary
    """
    try:
        if not MANIFEST_PATH.exists():
            logger.info("Manifest does not exist, creating new one")
            return {"documents": []}

        with open(MANIFEST_PATH) as f:
            manifest = yaml.safe_load(f)

        logger.info(f"Loaded manifest with {len(manifest.get('documents', []))} documents")

        return manifest

    except Exception as e:
        logger.error(f"Error loading manifest: {e}", exc_info=True)
        return {"documents": []}


def save_manifest(manifest: dict) -> bool:
    """
    Save the document manifest.

    Args:
        manifest: Manifest dictionary

    Returns:
        True if successful
    """
    try:
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

        with open(MANIFEST_PATH, "w") as f:
            yaml.dump(manifest, f, default_flow_style=False)

        logger.info(f"Saved manifest with {len(manifest.get('documents', []))} documents")

        return True

    except Exception as e:
        logger.error(f"Error saving manifest: {e}", exc_info=True)
        return False


async def update_manifest(document_data: dict) -> bool:
    """
    Update the manifest with a new document.

    Args:
        document_data: Document data to add

    Returns:
        True if successful
    """
    try:
        manifest = load_manifest()

        # Check if document already exists
        document_id = document_data.get("id")
        if document_data.get("title"):
            # Use title as ID if not provided
            document_id = document_data["title"]

        # Update or add document
        documents = manifest.get("documents", [])

        # Check for existing document with same title
        existing_index = None
        for i, doc in enumerate(documents):
            if doc.get("title") == document_data.get("title"):
                existing_index = i
                break

        if existing_index is not None:
            # Update existing document
            documents[existing_index] = document_data
            logger.info(f"Updated existing document in manifest: {document_data.get('title')}")
        else:
            # Add new document
            documents.append(document_data)
            logger.info(f"Added new document to manifest: {document_data.get('title')}")

        manifest["documents"] = documents

        return save_manifest(manifest)

    except Exception as e:
        logger.error(f"Error updating manifest: {e}", exc_info=True)
        return False


def get_document_status(title: str) -> str | None:
    """
    Get the status of a document from the manifest.

    Args:
        title: Document title

    Returns:
        Document status or None if not found
    """
    manifest = load_manifest()

    for doc in manifest.get("documents", []):
        if doc.get("title") == title:
            return doc.get("status")

    return None


def get_all_documents() -> list[dict]:
    """
    Get all documents from the manifest.

    Returns:
        List of document dictionaries
    """
    manifest = load_manifest()
    return manifest.get("documents", [])
