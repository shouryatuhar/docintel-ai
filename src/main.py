"""Unified CLI entrypoint for DocIntel AI."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from .outline_extractor import write_outline_json
    from .output_formatter import build_output_json
    from .pdf_reader import extract_text_by_page
    from .relevance_scorer import rank_sections
    from .section_splitter import split_sections
except ImportError:  # pragma: no cover - supports direct CLI execution
    from outline_extractor import write_outline_json
    from output_formatter import build_output_json
    from pdf_reader import extract_text_by_page
    from relevance_scorer import rank_sections
    from section_splitter import split_sections

INPUT_MANIFEST = "challenge1b_input.json"
PDF_SUFFIX = ".pdf"


def log(message: str) -> None:
    """Print a timestamped progress line to stdout."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{timestamp}] {message}", flush=True)


def list_pdfs(input_dir: Path) -> list[Path]:
    """Return sorted PDF paths from a directory."""
    return sorted(path for path in input_dir.iterdir() if path.suffix.lower() == PDF_SUFFIX)


def run_outline_mode(input_dir: Path, output_dir: Path) -> int:
    """Extract heading outlines for all PDFs in the input directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pdfs = list_pdfs(input_dir)
    if not pdfs:
        log(f"No PDF files found in {input_dir}")
        return 1

    log(f"Outline mode: processing {len(pdfs)} PDF(s)")
    failures = 0
    for pdf_path in pdfs:
        output_path = output_dir / f"{pdf_path.stem}.json"
        try:
            log(f"Extracting outline: {pdf_path.name}")
            write_outline_json(pdf_path, output_path)
            log(f"Wrote {output_path}")
        except Exception as exc:  # noqa: BLE001 — skip corrupt PDFs gracefully
            failures += 1
            log(f"Skipped {pdf_path.name}: {exc}")

    log(f"Outline mode complete ({len(pdfs) - failures} ok, {failures} failed)")
    return 0 if failures < len(pdfs) else 1


def load_persona_input(input_dir: Path) -> dict:
    """Load and validate persona mode manifest from the input directory."""
    manifest_path = input_dir / INPUT_MANIFEST
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing {INPUT_MANIFEST} in {input_dir}")

    with manifest_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    for key in ("persona", "job_to_be_done"):
        if key not in payload:
            raise ValueError(f"Manifest must include '{key}'")

    return payload


def run_persona_mode(input_dir: Path, output_dir: Path) -> int:
    """Run persona-driven section ranking for a PDF collection."""
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_persona_input(input_dir)
    persona = str(manifest["persona"])
    job = str(manifest["job_to_be_done"])

    document_names = manifest.get("documents")
    if document_names:
        pdf_paths = [input_dir / name for name in document_names]
    else:
        pdf_paths = list_pdfs(input_dir)

    pdf_paths = [path for path in pdf_paths if path.exists() and path.suffix.lower() == PDF_SUFFIX]
    if not pdf_paths:
        log(f"No PDF files found in {input_dir}")
        return 1

    log(f"Persona mode: {persona!r} — {len(pdf_paths)} document(s)")
    all_sections: list[dict] = []
    input_documents: list[str] = []
    failures = 0

    for pdf_path in pdf_paths:
        try:
            log(f"Reading {pdf_path.name}")
            page_count = len(extract_text_by_page(pdf_path))
            log(f"Parsed {page_count} page(s) from {pdf_path.name}")
            sections = split_sections(pdf_path.name, pdf_path)
            log(f"Found {len(sections)} section(s) in {pdf_path.name}")
            all_sections.extend(sections)
            input_documents.append(pdf_path.name)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            log(f"Skipped {pdf_path.name}: {exc}")

    if not all_sections:
        log("No sections extracted; aborting")
        return 1

    log("Ranking sections by relevance")
    ranked = rank_sections(all_sections, persona, job)
    timestamp = datetime.now(timezone.utc).isoformat()
    result = build_output_json(input_documents, persona, job, ranked, timestamp)

    output_path = output_dir / "challenge1b_output.json"
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=4, ensure_ascii=False)

    log(f"Wrote {output_path} ({len(ranked)} sections)")
    log(f"Persona mode complete ({failures} file(s) skipped)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Configure CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="DocIntel AI — offline PDF outline extraction and persona-driven ranking",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=("outline", "persona"),
        help="Processing mode: outline or persona",
    )
    parser.add_argument("--input", required=True, type=Path, help="Input directory path")
    parser.add_argument("--output", required=True, type=Path, help="Output directory path")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse CLI args and dispatch to the selected processing mode."""
    parser = build_parser()
    args = parser.parse_args(argv)

    input_dir = args.input.resolve()
    output_dir = args.output.resolve()

    if not input_dir.is_dir():
        log(f"Input directory does not exist: {input_dir}")
        return 1

    log(f"Starting DocIntel AI in {args.mode} mode")
    if args.mode == "outline":
        return run_outline_mode(input_dir, output_dir)
    return run_persona_mode(input_dir, output_dir)


if __name__ == "__main__":
    sys.exit(main())
