from ingestion.models import ExtractedPage
from ingestion.text_cleaner import clean_pages, normalize_page_text


def test_normalize_page_text_repairs_common_artifacts() -> None:
    text = "Business analy-\nsis\u00a0practice.\n\n\n\nNext paragraph."
    cleaned = normalize_page_text(text)

    assert "analysis practice." in cleaned
    assert "\u00a0" not in cleaned
    assert "\n\n\n" not in cleaned


def test_clean_pages_removes_repeated_margins() -> None:
    pages = [
        ExtractedPage(
            page_number=page_number,
            text=f"Repeated Header\n\nUnique body {page_number}\n\nRepeated Footer",
            character_count=60,
        )
        for page_number in range(1, 6)
    ]

    cleaned = clean_pages(pages)

    assert all("Repeated Header" not in page.text for page in cleaned)
    assert all("Repeated Footer" not in page.text for page in cleaned)
    assert all("Unique body" in page.text for page in cleaned)
