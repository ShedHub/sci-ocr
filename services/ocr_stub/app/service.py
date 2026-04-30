from pathlib import Path
from datetime import UTC, datetime
from threading import Lock, Thread
from time import perf_counter
from uuid import uuid4

from shared.contracts.ocr import (
    OcrJobStartResponse,
    OcrJobStatusResponse,
    OcrReadyResponse,
    OcrRequest,
    OcrResponse,
)


SERVICE_NAME = "ocr_stub"
MODEL_NAME = "ocr_stub"
MODEL_VERSION = "0.1.0"
_jobs: dict[str, dict] = {}
_jobs_lock = Lock()


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def get_status() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


def get_ready() -> OcrReadyResponse:
    return OcrReadyResponse(
        status="ready",
        service=SERVICE_NAME,
        model=MODEL_NAME,
        version=MODEL_VERSION,
    )


def validate_crop_path(image_path: str) -> None:
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"image_path does not exist or is not a file: {image_path}")


def build_stub_content(request: OcrRequest) -> str:
    if request.recognition_task == "table":
        return (
            "| source | block_id | role |\n"
            "| --- | --- | --- |\n"
            f"| ocr_stub | {request.block_id} | {request.content_role} |"
        )

    if request.recognition_task == "formula":
        escaped_block_id = request.block_id.replace("_", "\\_")
        return f"\\mathrm{{ocr\\_stub}}_{{{escaped_block_id}}}"

    if request.content_role == "title":
        return f"# OCR stub text for {request.block_id}"

    if request.content_role == "heading":
        return f"## OCR stub text for {request.block_id}"

    return f"OCR stub text for {request.block_id}"


def run_ocr(request: OcrRequest) -> OcrResponse:
    started = perf_counter()
    validate_crop_path(request.image_path)

    return OcrResponse(
        status="completed",
        job_id=request.job_id,
        document_id=request.document_id,
        page_number=request.page_number,
        block_id=request.block_id,
        content_role=request.content_role,
        recognition_task=request.recognition_task,
        format=request.requested_format,
        content=build_stub_content(request),
        confidence=1.0,
        model={
            "name": MODEL_NAME,
            "version": MODEL_VERSION,
            "backend": SERVICE_NAME,
            "metadata": {},
        },
        warnings=[
            "ocr_stub validated the crop path but did not run real OCR"
        ],
        error=None,
        service_time_ms=int((perf_counter() - started) * 1000),
    )


def _elapsed_seconds(job: dict) -> float:
    start = job.get("started_perf") or job["submitted_perf"]
    end = job.get("completed_perf") or perf_counter()
    return max(0.0, end - start)


def _job_status_response(task_id: str, job: dict) -> OcrJobStatusResponse:
    return OcrJobStatusResponse(
        task_id=task_id,
        status=job["status"],
        stage=job["stage"],
        job_id=job["request"].job_id,
        document_id=job["request"].document_id,
        page_number=job["request"].page_number,
        block_id=job["request"].block_id,
        submitted_at=job["submitted_at"],
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        last_heartbeat_at=job["last_heartbeat_at"],
        elapsed_seconds=_elapsed_seconds(job),
        message=job.get("message", ""),
        result=job.get("result"),
        error=job.get("error"),
    )


def _set_job(task_id: str, **updates) -> None:
    with _jobs_lock:
        _jobs[task_id].update(updates)


def _run_job(task_id: str) -> None:
    _set_job(
        task_id,
        status="running",
        stage="recognizing",
        started_at=utc_now(),
        started_perf=perf_counter(),
        last_heartbeat_at=utc_now(),
        message="OCR stub recognition running",
    )
    try:
        with _jobs_lock:
            request = _jobs[task_id]["request"]
        result = run_ocr(request)
        _set_job(
            task_id,
            status="completed",
            stage="completed",
            completed_at=utc_now(),
            completed_perf=perf_counter(),
            last_heartbeat_at=utc_now(),
            message="OCR stub recognition completed",
            result=result,
        )
    except Exception as exc:
        _set_job(
            task_id,
            status="failed",
            stage="failed",
            completed_at=utc_now(),
            completed_perf=perf_counter(),
            last_heartbeat_at=utc_now(),
            message="OCR stub recognition failed",
            error=str(exc),
        )


def start_ocr_job(request: OcrRequest) -> OcrJobStartResponse:
    task_id = str(uuid4())
    now = utc_now()
    with _jobs_lock:
        _jobs[task_id] = {
            "request": request,
            "status": "queued",
            "stage": "queued",
            "submitted_at": now,
            "submitted_perf": perf_counter(),
            "last_heartbeat_at": now,
            "message": "OCR job queued",
        }

    Thread(target=_run_job, args=(task_id,), daemon=True).start()
    return OcrJobStartResponse(
        status="queued",
        task_id=task_id,
        job_id=request.job_id,
        page_number=request.page_number,
        block_id=request.block_id,
        submitted_at=now,
    )


def get_ocr_job_status(task_id: str) -> OcrJobStatusResponse:
    with _jobs_lock:
        job = _jobs.get(task_id)
        if job is None:
            raise KeyError(task_id)
        snapshot = dict(job)
    return _job_status_response(task_id, snapshot)
