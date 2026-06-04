"""Rank document sections by relevance to persona and job intent."""

from __future__ import annotations

from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

TOP_SECTIONS = 5


def rank_sections(
    sections: list[dict[str, Any]],
    persona: str,
    job: str,
    top_n: int = TOP_SECTIONS,
) -> list[dict[str, Any]]:
    """Score sections with TF-IDF cosine similarity and return top matches."""
    if not sections:
        return []

    combined_query = f"{persona} {job}".strip()
    texts = [
        f"{section['section_title']} {section['section_title']} {section['text']}".strip()
        for section in sections
    ]
    vectorizer = TfidfVectorizer(stop_words="english")
    vectors = vectorizer.fit_transform([combined_query] + texts)
    similarities = cosine_similarity(vectors[0:1], vectors[1:]).flatten()

    for index, score in enumerate(similarities):
        sections[index]["score"] = float(score)

    ranked = sorted(sections, key=lambda item: item["score"], reverse=True)
    for rank, section in enumerate(ranked[:top_n], start=1):
        section["importance_rank"] = rank
    return ranked[:top_n]
