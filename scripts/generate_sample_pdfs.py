#!/usr/bin/env python3
"""Generate minimal sample PDFs for demos (stdlib only)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "samples" / "input"
PERSONA_DIR = ROOT / "samples" / "persona"


def _escape_pdf_text(text: str) -> str:
    """Escape parentheses and backslashes for PDF string literals."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_simple_pdf(path: Path, lines: list[tuple[str, int, bool]]) -> None:
    """Write a single-page PDF with positioned text lines."""
    stream_parts = ["BT"]
    y = 750
    for text, size, bold in lines:
        font = "/F2" if bold else "/F1"
        stream_parts.append(f"{font} {size} Tf 72 {y} Td ({_escape_pdf_text(text)}) Tj")
        y -= max(28, int(size * 2))
    stream_parts.append("ET")
    stream = "\n".join(stream_parts).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>"
        ),
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
    ]

    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_start = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode()
    pdf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n"
    ).encode()
    path.write_bytes(pdf)


def main() -> None:
    """Generate sample PDFs and persona manifest."""
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    PERSONA_DIR.mkdir(parents=True, exist_ok=True)
    (ROOT / "samples" / "output").mkdir(parents=True, exist_ok=True)
    (PERSONA_DIR / "output").mkdir(parents=True, exist_ok=True)

    guide_lines = [
        ("Product Guide", 20, True),
        ("Introduction", 14, True),
        ("This guide explains core features and setup steps for new users.", 11, False),
        ("Key Features", 14, True),
        ("Offline processing, heading extraction, and persona-driven ranking.", 11, False),
        ("Summary", 12, True),
        ("DocIntel AI runs entirely on CPU with no external services.", 11, False),
    ]
    write_simple_pdf(INPUT_DIR / "demo_guide.pdf", guide_lines)
    write_simple_pdf(INPUT_DIR / "quick_start.pdf", guide_lines)

    write_simple_pdf(
        PERSONA_DIR / "destinations.pdf",
        [
            ("Coastal Adventures", 16, True),
            (
                "Beach hopping along the Mediterranean includes Nice and Antibes. "
                "Plan sailing and snorkeling for a four-day college trip.",
                11,
                False,
            ),
        ],
    )
    write_simple_pdf(
        PERSONA_DIR / "packing_tips.pdf",
        [
            ("General Packing Tips", 16, True),
            (
                "Pack layers, travel-sized toiletries, and reusable bags. "
                "Bring a first aid kit and document copies for group travel.",
                11,
                False,
            ),
        ],
    )

    manifest = {
        "persona": "Travel Planner",
        "job_to_be_done": "Plan a trip of 4 days for a group of 10 college friends.",
        "documents": ["destinations.pdf", "packing_tips.pdf"],
    }
    with (PERSONA_DIR / "challenge1b_input.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")

    print(f"Wrote samples under {ROOT / 'samples'}")


if __name__ == "__main__":
    main()
