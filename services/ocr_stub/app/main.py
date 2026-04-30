from fastapi import FastAPI, HTTPException

from shared.contracts.ocr import (
    OcrJobStartResponse,
    OcrJobStatusResponse,
    OcrReadyResponse,
    OcrRequest,
    OcrResponse,
)

from .service import get_ocr_job_status, get_ready, get_status, run_ocr, start_ocr_job


app = FastAPI(title="ocr_stub")


@app.get("/health")
def health() -> dict[str, str]:
    return get_status()


@app.get("/ready")
def ready() -> OcrReadyResponse:
    return get_ready()


@app.post("/ocr", response_model=OcrResponse)
def ocr(request: OcrRequest) -> OcrResponse:
    try:
        return run_ocr(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/ocr/jobs", response_model=OcrJobStartResponse)
def start_job(request: OcrRequest) -> OcrJobStartResponse:
    return start_ocr_job(request)


@app.get("/ocr/jobs/{task_id}", response_model=OcrJobStatusResponse)
def job_status(task_id: str) -> OcrJobStatusResponse:
    try:
        return get_ocr_job_status(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"OCR job not found: {task_id}") from exc
