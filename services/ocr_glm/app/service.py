import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Lock, Thread
from time import perf_counter
from typing import Any
from uuid import uuid4

from shared.contracts.ocr import (
    OcrJobStartResponse,
    OcrJobStatusResponse,
    OcrReadyResponse,
    OcrRequest,
    OcrResponse,
)


SERVICE_NAME = "ocr_glm"
MODEL_NAME = "GLM-OCR"
MODEL_VERSION = "local"
DEFAULT_MODEL_DIR = "/models/ocr/glm-ocr"
DEFAULT_MAX_NEW_TOKENS = 8192
TASK_PROMPTS = {
    "text": "Text Recognition:",
    "table": "Table Recognition:",
    "formula": "Formula Recognition:",
}
REQUIRED_MODEL_FILES = (
    "config.json",
    "generation_config.json",
    "model.safetensors",
    "preprocessor_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
)

_processor = None
_model = None
_torch = None
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = Lock()
_executor = ThreadPoolExecutor(max_workers=int(os.getenv("OCR_JOB_MAX_WORKERS", "1")))


class GlmOcrUnavailable(RuntimeError):
    """Raised when the local GLM-OCR runtime or model files are not ready."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def get_job_heartbeat_interval_seconds() -> float:
    return float(os.getenv("OCR_JOB_HEARTBEAT_INTERVAL_SECONDS", "15"))


def get_model_dir() -> Path:
    return Path(os.getenv("OCR_MODEL_DIR", DEFAULT_MODEL_DIR))


def get_max_new_tokens() -> int:
    value = os.getenv("OCR_MAX_NEW_TOKENS")
    if value is None:
        return DEFAULT_MAX_NEW_TOKENS

    try:
        parsed = int(value)
    except ValueError as exc:
        raise GlmOcrUnavailable(f"OCR_MAX_NEW_TOKENS must be an integer: {value!r}") from exc

    if parsed < 1:
        raise GlmOcrUnavailable("OCR_MAX_NEW_TOKENS must be greater than zero")
    return parsed


def get_status() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


def validate_model_files() -> Path:
    model_dir = get_model_dir()
    if not model_dir.is_dir():
        raise GlmOcrUnavailable(f"model directory does not exist: {model_dir}")

    missing_files = [
        filename for filename in REQUIRED_MODEL_FILES if not (model_dir / filename).is_file()
    ]
    if missing_files:
        raise GlmOcrUnavailable(
            f"model directory is missing required files: {', '.join(missing_files)}"
        )
    return model_dir


def load_model() -> tuple[Any, Any, Any]:
    global _processor, _model, _torch
    if _processor is not None and _model is not None and _torch is not None:
        return _processor, _model, _torch

    model_dir = validate_model_files()
    try:
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        _processor = AutoProcessor.from_pretrained(str(model_dir))
        _model = AutoModelForImageTextToText.from_pretrained(
            pretrained_model_name_or_path=str(model_dir),
            torch_dtype="auto",
            device_map="auto",
        )
        _model.eval()
        _torch = torch
    except Exception as exc:
        raise GlmOcrUnavailable(f"failed to load {MODEL_NAME} from {model_dir}: {exc}") from exc

    return _processor, _model, _torch


def get_ready() -> OcrReadyResponse:
    validate_model_files()
    load_model()
    return OcrReadyResponse(
        status="ready",
        service=SERVICE_NAME,
        model=MODEL_NAME,
        version=MODEL_VERSION,
    )


def validate_crop_path(image_path: str) -> Path:
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"image_path does not exist or is not a file: {image_path}")
    return path


def prompt_for_task(recognition_task: str) -> str:
    try:
        return TASK_PROMPTS[recognition_task]
    except KeyError as exc:
        raise ValueError(f"Unsupported GLM-OCR recognition task: {recognition_task}") from exc


def build_messages(image_path: Path, request: OcrRequest) -> list[dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "url": str(image_path.resolve()),
                },
                {
                    "type": "text",
                    "text": prompt_for_task(request.recognition_task),
                },
            ],
        }
    ]


def generate_content(image_path: Path, request: OcrRequest) -> str:
    processor, model, torch = load_model()
    messages = build_messages(image_path, request)

    try:
        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        ).to(model.device)
        inputs.pop("token_type_ids", None)

        with torch.inference_mode():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=get_max_new_tokens(),
            )

        prompt_length = inputs["input_ids"].shape[1]
        return processor.decode(
            generated_ids[0][prompt_length:],
            skip_special_tokens=True,
        ).strip()
    except Exception as exc:
        raise ValueError(f"{MODEL_NAME} inference failed for {image_path}: {exc}") from exc


def strip_markdown_code_fence(value: str) -> str:
    text = value.strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def strip_latex_display_wrapper(value: str) -> str:
    text = value.strip()
    changed = True
    while changed:
        changed = False
        for left, right in (("$$", "$$"), ("\\[", "\\]")):
            if text.startswith(left) and text.endswith(right):
                text = text[len(left) : len(text) - len(right)].strip()
                changed = True
    return text


def normalize_recognized_content(content: str, request: OcrRequest) -> str:
    text = strip_markdown_code_fence(content)
    if request.recognition_task == "formula":
        text = strip_latex_display_wrapper(text)
    return text.strip()


def run_ocr(request: OcrRequest) -> OcrResponse:
    started = perf_counter()
    image_path = validate_crop_path(request.image_path)
    content = normalize_recognized_content(generate_content(image_path, request), request)

    return OcrResponse(
        status="completed",
        job_id=request.job_id,
        document_id=request.document_id,
        page_number=request.page_number,
        block_id=request.block_id,
        content_role=request.content_role,
        recognition_task=request.recognition_task,
        format=request.requested_format,
        content=content,
        confidence=None,
        model={
            "name": MODEL_NAME,
            "version": MODEL_VERSION,
            "backend": SERVICE_NAME,
            "metadata": {
                "model_dir": str(get_model_dir()),
                "max_new_tokens": get_max_new_tokens(),
            },
        },
        warnings=[],
        error=None,
        service_time_ms=int((perf_counter() - started) * 1000),
    )


def _elapsed_seconds(job: dict[str, Any]) -> float:
    start = job.get("started_perf") or job["submitted_perf"]
    end = job.get("completed_perf") or perf_counter()
    return max(0.0, end - start)


def _job_status_response(task_id: str, job: dict[str, Any]) -> OcrJobStatusResponse:
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


def _set_job(task_id: str, **updates: Any) -> None:
    with _jobs_lock:
        _jobs[task_id].update(updates)


def _heartbeat_until_stopped(task_id: str, stop_event: Event) -> None:
    interval = get_job_heartbeat_interval_seconds()
    while not stop_event.wait(interval):
        _set_job(
            task_id,
            last_heartbeat_at=utc_now(),
            message="GLM-OCR model.generate is still running",
        )


def _run_job(task_id: str) -> None:
    _set_job(
        task_id,
        status="running",
        stage="generating",
        started_at=utc_now(),
        started_perf=perf_counter(),
        last_heartbeat_at=utc_now(),
        message="GLM-OCR generation started",
    )
    stop_event = Event()
    ticker = Thread(target=_heartbeat_until_stopped, args=(task_id, stop_event), daemon=True)
    ticker.start()
    try:
        with _jobs_lock:
            request = _jobs[task_id]["request"]
        result = run_ocr(request)
        stop_event.set()
        _set_job(
            task_id,
            status="completed",
            stage="completed",
            completed_at=utc_now(),
            completed_perf=perf_counter(),
            last_heartbeat_at=utc_now(),
            message="GLM-OCR generation completed",
            result=result,
        )
    except Exception as exc:
        stop_event.set()
        _set_job(
            task_id,
            status="failed",
            stage="failed",
            completed_at=utc_now(),
            completed_perf=perf_counter(),
            last_heartbeat_at=utc_now(),
            message="GLM-OCR generation failed",
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

    _executor.submit(_run_job, task_id)
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
