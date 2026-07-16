from __future__ import annotations

from pathlib import Path

from pliris.config.settings import get_settings
from pliris.database.supabase_client import get_supabase_admin_client


class KnowledgeBaseStorage:
    """Private Supabase Storage operations for source PDFs."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = get_supabase_admin_client()
        self.bucket = self.settings.supabase_storage_bucket

    def build_storage_path(self, document_id: str, filename: str) -> str:
        safe_filename = Path(filename).name
        return f"{document_id}/{safe_filename}"

    def upload_pdf(
        self,
        source_path: Path,
        *,
        document_id: str,
    ) -> str:
        storage_path = self.build_storage_path(document_id, source_path.name)

        self.client.storage.from_(self.bucket).upload(
            path=storage_path,
            file=source_path.read_bytes(),
            file_options={
                "content-type": "application/pdf",
                "upsert": "true",
            },
        )
        return storage_path

    def remove(self, storage_path: str) -> None:
        self.client.storage.from_(self.bucket).remove([storage_path])
