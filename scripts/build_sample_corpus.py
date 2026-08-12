"""Build the redistributable sample PDF from its tracked Markdown source."""

from __future__ import annotations

import argparse
from pathlib import Path

import pymupdf

DEFAULT_SOURCE = Path("data/sample/public_ba_primer.md")
DEFAULT_OUTPUT = Path("data/sample/Pliris_Public_BA_Primer.pdf")


def build_pdf(source: Path, output: Path) -> None:
    text = source.read_text(encoding="utf-8")
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    cursor = 56.0

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            cursor += 8
            continue
        if line.startswith("# "):
            font_size, line = 19, line[2:]
        elif line.startswith("## "):
            font_size, line = 14, line[3:]
        else:
            font_size = 10

        height = 32 if font_size >= 14 else 48
        if cursor + height > 790:
            page = document.new_page(width=595, height=842)
            cursor = 56
        rect = pymupdf.Rect(56, cursor, 539, cursor + height)
        remainder = page.insert_textbox(
            rect,
            line,
            fontsize=font_size,
            fontname="helv",
            lineheight=1.25,
        )
        if remainder < 0:
            raise ValueError(f"Sample line did not fit in its PDF text box: {line[:40]}")
        cursor += height

    output.parent.mkdir(parents=True, exist_ok=True)
    document.set_metadata(
        {
            "title": "Pliris Public Business Analysis Primer",
            "author": "Pliris BA Bot project",
            "subject": "Redistributable Phase 8 sample corpus",
            "creator": "scripts.build_sample_corpus",
            "producer": "PyMuPDF",
            "creationDate": "D:20260812000000Z",
            "modDate": "D:20260812000000Z",
        }
    )
    document.save(output, garbage=4, deflate=True, clean=True, no_new_id=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build_pdf(args.source, args.output)
    print(f"Built {args.output}")


if __name__ == "__main__":
    main()
