"""PDF heading detection and outline extraction using font analysis."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer

from heading_logic import (
    MIN_HEADING_SCORE,
    MIN_LETTER_COUNT,
    clean_heading,
    compute_size_thresholds,
    extract_font_styles,
    is_skipped_line,
    iter_heading_candidates,
    level_for_size,
    line_font_info,
    merge_multiline_headings,
    normalize_for_match,
    score_heading,
)


def extract_headings_and_title(pdf_path: str | Path) -> tuple[str, list[dict[str, Any]]]:
    """Extract document title and heading outline (H1–H3) from a PDF."""
    path = str(pdf_path)
    thresholds = compute_size_thresholds(extract_font_styles(path))
    candidates = list(iter_heading_candidates(path, thresholds))
    qualified = [item for item in candidates if item["score"] >= MIN_HEADING_SCORE]
    headings = merge_multiline_headings(qualified)

    title_candidate: str | None = None
    for candidate in qualified:
        if candidate["page"] == 1 and candidate["level"] == "H1":
            title_candidate = candidate["text"]
            break

    title = title_candidate or (headings[0]["text"] if headings else "")
    return title, headings


def iter_classified_lines(
    pdf_path: str | Path,
    thresholds: dict[str, float] | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield each layout line as heading or body for section splitting."""
    path = str(pdf_path)
    if thresholds is None:
        thresholds = compute_size_thresholds(extract_font_styles(path))

    for page_number, page_layout in enumerate(extract_pages(path), start=1):
        for element in page_layout:
            if not isinstance(element, LTTextContainer):
                continue
            for line in element:
                raw_text = line.get_text().strip()
                if is_skipped_line(raw_text):
                    continue
                cleaned = clean_heading(raw_text)
                if not cleaned:
                    continue

                font_info = line_font_info(line)
                if font_info is None:
                    yield {"page": page_number, "text": cleaned, "is_heading": False}
                    continue

                size, is_bold = font_info
                norm_line = normalize_for_match(cleaned)
                level = level_for_size(size, thresholds)
                heading_score = score_heading(norm_line, is_bold)
                is_heading = (
                    level is not None
                    and heading_score >= MIN_HEADING_SCORE
                    and len(re.findall(r"[A-Za-z]", cleaned)) >= MIN_LETTER_COUNT
                )
                yield {
                    "page": page_number,
                    "text": cleaned,
                    "is_heading": is_heading,
                    "size": size,
                    "is_bold": is_bold,
                    "level": level or "",
                }


def extract_outline(pdf_path: str | Path) -> dict[str, Any]:
    """Build outline JSON payload for a single PDF."""
    title, outline = extract_headings_and_title(pdf_path)
    return {"title": title, "outline": outline}


def write_outline_json(pdf_path: str | Path, output_path: str | Path) -> None:
    """Write outline JSON for one PDF to disk."""
    payload = extract_outline(pdf_path)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
