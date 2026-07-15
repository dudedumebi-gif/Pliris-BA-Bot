"""Script to ingest documents into the knowledge base."""

import asyncio
import sys
from pathlib import Path

from ingestion.run import process_directory, process_document


async def main():
    """Main ingestion script."""
    if len(sys.argv) < 2:
        print("Usage: python ingest_documents.py <file_or_directory>")
        sys.exit(1)

    path = sys.argv[1]
    path_obj = Path(path)

    if not path_obj.exists():
        print(f"Error: Path does not exist: {path}")
        sys.exit(1)

    print(f"Ingesting documents from: {path}")

    if path_obj.is_dir():
        results = await process_directory(path)
    else:
        metadata = {"title": path_obj.stem, "source": "manual_upload", "type": "document"}
        results = [await process_document(path, metadata)]

    # Print summary
    successful = sum(1 for r in results if r.get("status") == "success")
    failed = sum(1 for r in results if r.get("status") == "error")

    print("\nIngestion complete:")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")

    if failed > 0:
        print("\nFailed documents:")
        for result in results:
            if result.get("status") == "error":
                print(f"  - {result['file_path']}: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(main())
