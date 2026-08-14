"""
Web API for the PII Redaction Tool.

Exposes a REST endpoint that accepts .docx uploads, runs the
blackout redaction pipeline, and returns the redacted document
plus an entity map.
"""

import os
import uuid
import tempfile

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pipeline import run_redaction

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="PII Redaction Tool",
    description="Detect and redact PII from .docx documents using blackout bars",
    version="1.0.0",
)

# Cross-origin access (Vercel frontend → Render backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

SCRATCH = os.path.join(tempfile.gettempdir(), "pii_tool")
os.makedirs(SCRATCH, exist_ok=True)

# ---------------------------------------------------------------------------
# Preload the NLP model once at startup
# ---------------------------------------------------------------------------

print("[API] Loading spaCy model...")
from scanner import build_analyzer
from settings import NLP_MODEL
_analyzer = build_analyzer()
print(f"[API] Model '{NLP_MODEL}' ready.")

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "model": NLP_MODEL}


@app.post("/api/redact")
async def redact(file: UploadFile = File(...)):
    """Accept a .docx upload, redact it, and return results."""
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(400, "Only .docx files are accepted.")

    task_id = uuid.uuid4().hex[:8]
    work = os.path.join(SCRATCH, task_id)
    os.makedirs(work, exist_ok=True)

    input_path = os.path.join(work, file.filename)
    output_path = os.path.join(work, f"redacted_{file.filename}")
    map_path = os.path.join(work, "entity_map.json")

    with open(input_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        stats = run_redaction(
            input_path=input_path,
            output_path=output_path,
            mapping_path=map_path,
        )
    except Exception as exc:
        raise HTTPException(500, f"Redaction failed: {exc}")

    # Build preview from entity map
    import json
    preview = []
    if os.path.exists(map_path):
        with open(map_path, "r", encoding="utf-8") as f:
            entity_map = json.load(f)
        for entry in list(entity_map.values())[:20]:
            preview.append({
                "original": entry["original"],
                "replacement": entry["replacement"],
                "type": entry["type"],
            })

    return {
        "task_id": task_id,
        "stats": {
            "total_entities": stats["total_entities"],
            "unique_entities": stats["unique_entities"],
            "by_type": stats["by_type"],
            "definitions_extracted": stats["definitions_count"],
            "segments_processed": stats["segments_count"],
        },
        "downloads": {
            "redacted": f"/api/download/{task_id}/redacted_{file.filename}",
            "entity_map": f"/api/download/{task_id}/entity_map.json",
        },
        "preview": preview,
    }


@app.get("/api/download/{task_id}/{filename}")
async def download(task_id: str, filename: str):
    path = os.path.join(SCRATCH, task_id, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "File not found.")
    return FileResponse(path, filename=filename)


# ---------------------------------------------------------------------------
# Static frontend (production only — served from frontend/out/)
# ---------------------------------------------------------------------------

_frontend = os.path.join(os.path.dirname(__file__), "frontend", "out")
if os.path.isdir(_frontend):
    app.mount("/", StaticFiles(directory=_frontend, html=True), name="static")
