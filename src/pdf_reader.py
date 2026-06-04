"""PDF text extraction utilities."""

from __future__ import annotations

from pathlib import Path

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer


def extract_text_by_page(pdf_path: str | Path) -> list[str]:
    """Extract plain text for each page of a PDF."""
    pages: list[str] = []
    for page_layout in extract_pages(str(pdf_path)):
        page_text = ""
        for element in page_layout:
            if isinstance(element, LTTextContainer):
                page_text += element.get_text()
        pages.append(page_text.strip())
    return pages
