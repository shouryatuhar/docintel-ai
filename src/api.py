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
from .resume_fit import analyze_resume_fit
from .database import init_db, log_event, log_feedback, get_metrics

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


@app.on_event("startup")
def startup_db_init() -> None:
    """Initialize database tables on FastAPI startup."""
    init_db()



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
        filename, pdf_path = _save_upload(file, Path(temp_dir))
        try:
            res = extract_outline(pdf_path)
            event_id = log_event(
                workflow="outline",
                details={"filename": filename}
            )
            res["analysis_id"] = event_id
            return res
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
        res = build_output_json(input_documents, persona, job, ranked, timestamp)
        event_id = log_event(
            workflow="persona",
            details={
                "filenames": input_documents,
                "persona": persona,
                "job": job
            }
        )
        res["analysis_id"] = event_id
        return res


@app.post("/resume-fit")
@app.post("/api/resume-fit")
async def resume_fit(
    resume: UploadFile = File(...),
    job_description: str = Form(...),
) -> dict:
    """Check how well a resume matches a job description."""
    with TemporaryDirectory() as temp_dir:
        resume_name, pdf_path = _save_upload(resume, Path(temp_dir))
        try:
            result = analyze_resume_fit(resume_name, pdf_path, job_description)
            event_id = log_event(
                workflow="resume-fit",
                details={
                    "filename": resume_name,
                    "match_category": result["match_category"],
                    "match_score": result["match_score"],
                    "matched_count": len(result["matched_keywords"]),
                    "missing_count": len(result["missing_keywords"])
                }
            )
            result["analysis_id"] = event_id
            return result
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/feedback")
@app.post("/api/feedback")
async def feedback(payload: dict) -> dict:
    """Log user feedback (thumbs up/down) for an analysis."""
    analysis_id = payload.get("analysis_id")
    useful = payload.get("useful")
    if analysis_id is None or useful is None:
        raise HTTPException(status_code=400, detail="analysis_id and useful are required")
    success = log_feedback(int(analysis_id), bool(useful))
    return {"status": "success" if success else "failed"}


@app.get("/metrics")
@app.get("/api/metrics")
async def metrics() -> dict:
    """Retrieve raw metrics (real data only)."""
    try:
        return get_metrics()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
