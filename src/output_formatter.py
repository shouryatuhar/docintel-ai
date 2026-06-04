"""Build persona-mode output JSON matching the expected schema."""

from __future__ import annotations

import re
from typing import Any

REFINED_TEXT_MAX_LENGTH = 500


def trim_at_sentence_boundary(text: str, max_length: int = REFINED_TEXT_MAX_LENGTH) -> str:
    """Trim text to max_length, preferring the nearest prior sentence boundary."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_length:
        return cleaned

    window = cleaned[:max_length]
    for separator in (". ", "! ", "? ", ".\n", "!\n", "?\n"):
        position = window.rfind(separator)
        if position > 40:
            return window[: position + len(separator)].strip()

    last_space = window.rfind(" ")
    if last_space > 40:
        return window[:last_space].strip()
    return window.strip()


def build_output_json(
    input_documents: list[str],
    persona: str,
    job: str,
    ranked_sections: list[dict[str, Any]],
    processing_timestamp: str,
) -> dict[str, Any]:
    """Assemble the persona pipeline result payload."""
    extracted_sections: list[dict[str, Any]] = []
    subsection_analysis: list[dict[str, Any]] = []

    for section in ranked_sections:
        extracted_sections.append({
            "document": section["document"],
            "section_title": section["section_title"],
            "importance_rank": section["importance_rank"],
            "page_number": section["page"],
        })
        subsection_analysis.append({
            "document": section["document"],
            "refined_text": trim_at_sentence_boundary(section["text"]),
            "page_number": section["page"],
        })

    return {
        "metadata": {
            "input_documents": input_documents,
            "persona": persona,
            "job_to_be_done": job,
            "processing_timestamp": processing_timestamp,
        },
        "extracted_sections": extracted_sections,
        "subsection_analysis": subsection_analysis,
    }
