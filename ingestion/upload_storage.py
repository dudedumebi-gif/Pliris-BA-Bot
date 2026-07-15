"""Upload documents to storage."""

import logging
import uuid
from pathlib import Path

from pliris.database.supabase_client import get_client

logger = logging.getLogger(__name__)


async def upload_to_storage(file_path: str, bucket: str = "documents") -> str:
    """
    Upload a file to Supabase storage.

    Args:
        file_path: Path to the file to upload
        bucket: Storage bucket name

    Returns:
        Storage path of the uploaded file
    """
    try:
        client = get_client()
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Generate unique filename
        file_extension = file_path.suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        storage_path = f"{bucket}/{unique_filename}"

        # Read file content
        with open(file_path, "rb") as f:
            file_content = f.read()

        # Upload to Supabase storage
        client.storage.from_(bucket).upload(
            path=unique_filename,
            file=file_content,
            file_options={"content-type": "application/pdf"},
        )

        logger.info(f"Uploaded {file_path.name} to {storage_path}")

        return storage_path

    except Exception as e:
        logger.error(f"Error uploading to storage: {e}", exc_info=True)
        raise


async def download_from_storage(storage_path: str, local_path: str) -> str:
    """
    Download a file from Supabase storage.

    Args:
        storage_path: Path in storage
        local_path: Local path to save the file

    Returns:
        Local file path
    """
    try:
        client = get_client()

        # Parse storage path
        parts = storage_path.split("/")
        bucket = parts[0]
        filename = "/".join(parts[1:])

        # Download file
        data = client.storage.from_(bucket).download(filename)

        # Save to local path
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)

        with open(local_path, "wb") as f:
            f.write(data)

        logger.info(f"Downloaded {storage_path} to {local_path}")

        return str(local_path)

    except Exception as e:
        logger.error(f"Error downloading from storage: {e}", exc_info=True)
        raise


async def delete_from_storage(storage_path: str) -> bool:
    """
    Delete a file from Supabase storage.

    Args:
        storage_path: Path in storage

    Returns:
        True if successful
    """
    try:
        client = get_client()

        # Parse storage path
        parts = storage_path.split("/")
        bucket = parts[0]
        filename = "/".join(parts[1:])

        # Delete file
        client.storage.from_(bucket).remove([filename])

        logger.info(f"Deleted {storage_path} from storage")

        return True

    except Exception as e:
        logger.error(f"Error deleting from storage: {e}", exc_info=True)
        return False
