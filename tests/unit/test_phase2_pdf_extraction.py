from pathlib import Path

import fitz

from ingestion.pdf_extractor import extract_pdf


def test_extract_pdf_preserves_page_numbers(tmp_path: Path) -> None:
    path = tmp_path / "sample.pdf"

    document = fitz.open()
    for page_number in range(1, 4):
        page = document.new_page()
        page.insert_text((72, 72), f"Page {page_number} business analysis content.")
    document.save(path)
    document.close()

    extracted = extract_pdf(path)

    assert extracted.page_count == 3
    assert [page.page_number for page in extracted.pages] == [1, 2, 3]
    assert "business analysis" in extracted.pages[0].text.lower()
