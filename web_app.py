"""
Browser demo for the document processing agent.

This is what you show a client or record for a pitch video — drag in an
invoice, watch it get extracted and flagged live, no terminal required.

Run:
    uvicorn web_app:app --reload --port 8000
Then open http://localhost:8000 in your browser.
"""

import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from extractor import process_document
from export_csv import export as export_csv

app = FastAPI()

BASE_DIR = Path(__file__).parent
SAMPLES_DIR = BASE_DIR / "sample_documents"

INDEX_HTML = (BASE_DIR / "static" / "index.html").read_text()

# Serve sample images directly so the UI can show thumbnails / quick-load buttons
app.mount("/sample-files", StaticFiles(directory=SAMPLES_DIR), name="sample-files")


@app.get("/", response_class=HTMLResponse)
def index():
    return INDEX_HTML


@app.get("/api/samples")
def list_samples():
    files = sorted(p.name for p in SAMPLES_DIR.glob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg"})
    return {"samples": files}


class SampleRequest(BaseModel):
    filename: str


@app.post("/api/process_sample")
def process_sample(req: SampleRequest):
    # Guard against path traversal — only allow exact filenames that exist in SAMPLES_DIR
    valid_names = {p.name for p in SAMPLES_DIR.glob("*")}
    if req.filename not in valid_names:
        raise HTTPException(status_code=404, detail="Sample not found")
    try:
        return process_document(str(SAMPLES_DIR / req.filename))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/export.csv")
def download_export():
    """Lets the client download everything processed so far as a CSV."""
    csv_path = BASE_DIR / "data" / "export.csv"
    export_csv(str(csv_path))
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="No documents processed yet.")
    return FileResponse(
        csv_path,
        media_type="text/csv",
        filename="processed_documents.csv",
    )


@app.post("/process")
async def process(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        result = process_document(tmp_path)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
