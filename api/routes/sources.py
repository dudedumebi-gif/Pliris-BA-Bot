import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def get_sources():
    """
    Get all indexed documents/sources.
    """
    try:
        from pliris.database.repositories.documents import DocumentRepository

        repo = DocumentRepository()
        documents = await repo.get_all()

        return documents

    except Exception as exc:
        logger.error(f"Error fetching sources: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch sources"
        ) from exc


@router.get("/stats")
async def get_source_stats():
    """
    Get statistics about indexed documents.
    """
    try:
        from pliris.database.repositories.documents import DocumentRepository

        repo = DocumentRepository()
        stats = await repo.get_stats()

        return stats

    except Exception as exc:
        logger.error(f"Error fetching source stats: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch source statistics",
        ) from exc


@router.post("/upload")
async def upload_source(
    file: UploadFile = File(...),
    title: str = Form(...),
    source: str = Form(default=""),
    type: str = Form(default="text"),
    tags: str = Form(default=""),
):
    """
    Upload a new document for indexing.
    """
    try:
        from ingestion.manifest import update_manifest
        from ingestion.upload_storage import upload_to_storage

        # Upload file to storage
        file_path = await upload_to_storage(file)

        # Update manifest
        await update_manifest(
            {
                "title": title,
                "source": source,
                "type": type,
                "tags": tags.split(",") if tags else [],
                "file_path": file_path,
                "status": "pending",
            }
        )

        logger.info(f"Document uploaded: {title}")

        return {
            "status": "uploaded",
            "title": title,
            "file_path": file_path,
            "message": "Document uploaded successfully and will be processed shortly",
        }

    except Exception as exc:
        logger.error(f"Error uploading source: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to upload document"
        ) from exc


@router.get("/{source_id}")
async def get_source(source_id: str):
    """
    Get details for a specific source.
    """
    try:
        from pliris.database.repositories.documents import DocumentRepository

        repo = DocumentRepository()
        document = await repo.get_by_id(source_id)

        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

        return document

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error fetching source: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch source"
        ) from exc


@router.delete("/{source_id}")
async def delete_source(source_id: str):
    """
    Delete a source and its chunks.
    """
    try:
        from pliris.database.repositories.documents import DocumentRepository

        repo = DocumentRepository()
        await repo.delete(source_id)

        logger.info(f"Source deleted: {source_id}")

        return {"status": "deleted", "id": source_id}

    except Exception as exc:
        logger.error(f"Error deleting source: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete source"
        ) from exc
