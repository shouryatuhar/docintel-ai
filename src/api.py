"""FastAPI app for DocIntel AI web access."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .outline_extractor import extract_outline
from .output_formatter import build_output_json
from .relevance_scorer import rank_sections
from .section_splitter import split_sections

APP_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_FILE = APP_ROOT / "frontend" / "index.html"

app = FastAPI(title="DocIntel AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _validate_pdf_upload(upload: UploadFile) -> str:
    filename = upload.filename or "document.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail=f"{filename} is not a PDF file")
    return Path(filename).name


def _save_upload(upload: UploadFile, target_dir: Path) -> tuple[str, Path]:
    filename = _validate_pdf_upload(upload)
    output_path = target_dir / filename
    counter = 1
    while output_path.exists():
        output_path = target_dir / f"{counter}_{filename}"
        counter += 1
    with output_path.open("wb") as handle:
        shutil.copyfileobj(upload.file, handle)
    return filename, output_path


@app.get("/", response_class=FileResponse)
async def serve_frontend() -> FileResponse:
    """Serve the single-file frontend."""
    if not FRONTEND_FILE.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(FRONTEND_FILE)


@app.post("/outline")
@app.post("/api/outline")
async def outline(file: UploadFile = File(...)) -> dict:
    """Extract a title and heading outline from one PDF."""
    with TemporaryDirectory() as temp_dir:
        _, pdf_path = _save_upload(file, Path(temp_dir))
        try:
            return extract_outline(pdf_path)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/persona")
@app.post("/api/persona")
async def persona(
    files: list[UploadFile] = File(...),
    persona: str = Form(...),
    job: str = Form(...),
) -> dict:
    """Rank sections across uploaded PDFs for a persona and job."""
    if not files:
        raise HTTPException(status_code=400, detail="At least one PDF is required")

    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        all_sections: list[dict] = []
        input_documents: list[str] = []

        for upload in files:
            document_name, pdf_path = _save_upload(upload, temp_path)
            try:
                sections = split_sections(document_name, pdf_path)
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to process {document_name}: {exc}",
                ) from exc

            all_sections.extend(sections)
            input_documents.append(document_name)

        if not all_sections:
            raise HTTPException(status_code=400, detail="No sections extracted from PDFs")

        ranked = rank_sections(all_sections, persona, job)
        timestamp = datetime.now(timezone.utc).isoformat()
        return build_output_json(input_documents, persona, job, ranked, timestamp)
