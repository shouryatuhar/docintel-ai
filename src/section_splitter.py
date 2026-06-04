"""Split PDFs into sections using font-based heading detection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from heading_logic import (
    compute_size_thresholds,
    extract_font_styles,
    merge_multiline_headings,
)
from outline_extractor import iter_classified_lines


def split_sections(document_name: str, pdf_path: str | Path) -> list[dict[str, Any]]:
    """Split a PDF into sections keyed by detected headings."""
    thresholds = compute_size_thresholds(extract_font_styles(pdf_path))
    lines = list(iter_classified_lines(pdf_path, thresholds))
    sections: list[dict[str, Any]] = []
    current_title: str | None = None
    current_page = 1
    body_parts: list[str] = []
    preamble_parts: list[str] = []
    index = 0

    def flush_section() -> None:
        nonlocal current_title, body_parts
        if current_title and body_parts:
            sections.append({
                "document": document_name,
                "page": current_page,
                "section_title": current_title,
                "text": " ".join(body_parts).strip(),
            })
        body_parts = []

    while index < len(lines):
        line = lines[index]
        if line["is_heading"]:
            heading_batch: list[dict[str, Any]] = []
            while index < len(lines) and lines[index]["is_heading"]:
                entry = lines[index]
                heading_batch.append({
                    "level": entry["level"],
                    "text": entry["text"],
                    "page": entry["page"],
                    "size": entry["size"],
                    "is_bold": entry["is_bold"],
                    "score": 2,
                })
                index += 1

            merged = merge_multiline_headings(heading_batch)
            flush_section()
            if merged:
                current_title = merged[0]["text"]
                current_page = merged[0]["page"]
                body_parts = preamble_parts.copy()
                preamble_parts = []
            continue

        if current_title is None:
            preamble_parts.append(line["text"])
            index += 1
            continue
        body_parts.append(line["text"])
        index += 1

    flush_section()
    return sections
