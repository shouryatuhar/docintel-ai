"""Low-level PDF heading detection helpers."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterator
from typing import Any

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTChar, LTTextContainer

HEADING_KEYWORDS = frozenset({
    "introduction", "overview", "summary", "conclusion", "background",
    "objectives", "goals", "methodology", "results", "discussion",
    "appendix", "references", "table of contents", "executive summary",
    "key findings", "recommendations", "next steps", "faq", "contact",
})

MAX_LINE_LENGTH = 300
MAX_MERGED_HEADING_LENGTH = 120
MIN_LETTER_COUNT = 3
MIN_HEADING_SCORE = 2
DEFAULT_FONT_SIZES = (12.0, 11.0, 10.0)


def clean_heading(text: str) -> str:
    """Normalize whitespace and strip unsupported characters from heading text."""
    text = text.replace("\u00a0", " ")
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[^\x20-\x7E\u00A0-\u024F]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_for_match(text: str) -> str:
    """Lowercase and normalize text for keyword matching."""
    normalized = unicodedata.normalize("NFKD", text.lower()).replace("\u00a0", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def extract_font_styles(pdf_path: str) -> Counter[tuple[str, float]]:
    """Count (fontname, size) pairs across all lines in a PDF."""
    font_stats: Counter[tuple[str, float]] = Counter()
    for page_layout in extract_pages(pdf_path):
        for element in page_layout:
            if not isinstance(element, LTTextContainer):
                continue
            for text_line in element:
                try:
                    for char in text_line:
                        if isinstance(char, LTChar):
                            font_stats[(char.fontname, round(char.size, 1))] += 1
                except TypeError:
                    continue
    return font_stats


def compute_size_thresholds(font_stats: Counter[tuple[str, float]]) -> dict[str, float]:
    """Derive H1/H2/H3 font-size thresholds from document font frequency."""
    sorted_styles = sorted(
        [
            (style, count)
            for style, count in font_stats.items()
            if isinstance(style[1], (int, float))
        ],
        key=lambda item: (-item[1], -float(item[0][1])),
    )
    font_size_order = [float(style[0][1]) for style in sorted_styles]
    if not font_size_order:
        font_size_order = list(DEFAULT_FONT_SIZES)

    h1 = font_size_order[0]
    h2 = font_size_order[1] if len(font_size_order) > 1 else h1 - 1
    h3 = font_size_order[2] if len(font_size_order) > 2 else font_size_order[-1] - 1
    return {"H1": h1, "H2": h2, "H3": h3}


def line_font_info(line: Any) -> tuple[float, bool] | None:
    """Return dominant font size and bold flag for a layout line, or None."""
    try:
        line_fonts = [
            (char.fontname, round(char.size, 1))
            for char in line
            if isinstance(char, LTChar)
        ]
    except TypeError:
        return None
    if not line_fonts:
        return None
    sizes = [size for _, size in line_fonts]
    most_common_size = Counter(sizes).most_common(1)[0][0]
    is_bold = any("Bold" in name or "bold" in name for name, _ in line_fonts)
    return float(most_common_size), is_bold


def is_skipped_line(raw_text: str) -> bool:
    """Return True if a line should be ignored for heading detection."""
    if not raw_text or len(raw_text) > MAX_LINE_LENGTH:
        return True
    if re.fullmatch(r"[\s\d\.\-•·‣•‧●○□…‥]+", raw_text):
        return True
    return "table of contents" in raw_text.lower()


def score_heading(norm_line: str, is_bold: bool) -> int:
    """Score heading confidence: keyword match > bold > plain."""
    if any(keyword in norm_line for keyword in HEADING_KEYWORDS):
        return 3
    return 2 if is_bold else 1


def level_for_size(size: float, thresholds: dict[str, float]) -> str | None:
    """Map font size to H1/H2/H3, or None if below heading threshold."""
    if size >= thresholds["H1"]:
        return "H1"
    if size >= thresholds["H2"]:
        return "H2"
    if size >= thresholds["H3"]:
        return "H3"
    return None


def iter_heading_candidates(
    pdf_path: str,
    thresholds: dict[str, float] | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield raw heading candidate dicts per layout line before multi-line merge."""
    if thresholds is None:
        thresholds = compute_size_thresholds(extract_font_styles(pdf_path))

    for page_number, page_layout in enumerate(extract_pages(pdf_path), start=1):
        for element in page_layout:
            if not isinstance(element, LTTextContainer):
                continue
            for line in element:
                raw_text = line.get_text().strip()
                if is_skipped_line(raw_text):
                    continue
                font_info = line_font_info(line)
                if font_info is None:
                    continue

                size, is_bold = font_info
                cleaned = clean_heading(raw_text)
                norm_line = normalize_for_match(cleaned)
                if not cleaned or len(re.findall(r"[A-Za-z]", cleaned)) < MIN_LETTER_COUNT:
                    continue

                level = level_for_size(size, thresholds)
                if level is None:
                    continue

                yield {
                    "level": level,
                    "text": cleaned,
                    "page": page_number,
                    "size": size,
                    "is_bold": is_bold,
                    "score": score_heading(norm_line, is_bold),
                }


def merge_multiline_headings(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge consecutive continuation lines with matching size and bold."""
    if not candidates:
        return []

    merged: list[dict[str, Any]] = []
    buffer: dict[str, Any] | None = None

    for candidate in candidates:
        if buffer is None:
            buffer = dict(candidate)
            continue

        same_style = (
            buffer["page"] == candidate["page"]
            and buffer["size"] == candidate["size"]
            and buffer["is_bold"] == candidate["is_bold"]
            and buffer["level"] == candidate["level"]
        )
        combined = f"{buffer['text']} {candidate['text']}"
        continues_line = candidate["text"][:1].islower() if candidate["text"] else False
        if same_style and continues_line and len(combined) < MAX_MERGED_HEADING_LENGTH:
            buffer["text"] = combined
            buffer["score"] = max(buffer["score"], candidate["score"])
            continue

        merged.append(finalize_heading(buffer))
        buffer = dict(candidate)

    if buffer is not None:
        merged.append(finalize_heading(buffer))
    return merged


def finalize_heading(entry: dict[str, Any]) -> dict[str, Any]:
    """Strip internal fields used only during detection."""
    return {"level": entry["level"], "text": entry["text"], "page": entry["page"]}
