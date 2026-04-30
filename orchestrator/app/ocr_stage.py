"""
HTTP-backed OCR stage.

The orchestrator sends routed block crops to an external OCR worker and stores
raw and normalized OCR artifacts. Image and chart crops are recorded as pending
for the future vision service.
"""

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter, sleep

import httpx

from orchestrator.app.config import (
    OCR_ASYNC_ENABLED,
    OCR_JOB_HTTP_TIMEOUT_SECONDS,
    OCR_JOB_MAX_RUNTIME_SECONDS,
    OCR_JOB_POLL_INTERVAL_SECONDS,
    OCR_JOB_STALL_TIMEOUT_SECONDS,
    OCR_SERVICE_URL,
    OCR_TIMEOUT_SECONDS,
)
from orchestrator.app.job_metadata import append_log_line, write_json
from shared.contracts.ocr import (
    NormalizedOcrArtifact,
    OcrJobStartResponse,
    OcrJobStatusResponse,
    OcrReadyResponse,
    OcrRequest,
    OcrResponse,
)


class OcrServiceError(RuntimeError):
    """Raised when the external OCR service cannot complete a request."""


def _route(crop: dict) -> dict:
    return crop.get("routing", {})


def is_ocr_crop(crop: dict) -> bool:
    return _route(crop).get("target_service") == "ocr"


def is_vision_crop(crop: dict) -> bool:
    return _route(crop).get("target_service") == "vision"


def iter_page_crops(layout_asset_pages: list[dict]):
    for page in layout_asset_pages:
        for crop in page.get("crops", []):
            yield crop


def build_ocr_request(
    job_id: str,
    document_id: str,
    crop: dict,
) -> dict:
    route = _route(crop)
    request = OcrRequest(
        job_id=job_id,
        document_id=document_id,
        page_number=crop["page_number"],
        block_id=crop["block_id"],
        block_type=crop["type"],
        layout_label=crop.get("layout_label"),
        content_role=route["content_role"],
        recognition_task=route["recognition_task"],
        requested_format=route["requested_format"],
        image_path=crop["image_path"],
        bbox=tuple(crop["bbox"]),
        order=crop["order"],
    )
    return request.model_dump()


def check_ocr_service_ready(
    ocr_service_url: str = OCR_SERVICE_URL,
    timeout: float = OCR_TIMEOUT_SECONDS,
) -> dict:
    ready_url = f"{ocr_service_url.rstrip('/')}/ready"

    try:
        response = httpx.get(ready_url, timeout=timeout, trust_env=False)
        response.raise_for_status()
        payload = response.json()
        ready = OcrReadyResponse.model_validate(payload)
    except httpx.HTTPStatusError as exc:
        raise OcrServiceError(
            f"OCR service readiness check failed with HTTP "
            f"{exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise OcrServiceError(f"OCR service is not reachable at {ready_url}: {exc}") from exc
    except ValueError as exc:
        raise OcrServiceError(f"OCR service readiness response is not valid JSON: {exc}") from exc

    return ready.model_dump()


def call_ocr_service(
    request: dict,
    ocr_service_url: str = OCR_SERVICE_URL,
    timeout: float = OCR_TIMEOUT_SECONDS,
) -> dict:
    ocr_url = f"{ocr_service_url.rstrip('/')}/ocr"

    try:
        response = httpx.post(
            ocr_url,
            json=request,
            timeout=timeout,
            trust_env=False,
        )
        response.raise_for_status()
        payload = response.json()
        validated = OcrResponse.model_validate(payload)
    except httpx.HTTPStatusError as exc:
        raise OcrServiceError(
            f"OCR request for block {request.get('block_id')} failed with HTTP "
            f"{exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise OcrServiceError(
            f"OCR service request failed for block {request.get('block_id')} "
            f"at {ocr_url}: {exc}"
        ) from exc
    except ValueError as exc:
        raise OcrServiceError(
            f"OCR service response for block {request.get('block_id')} "
            f"is not valid JSON: {exc}"
        ) from exc

    payload = validated.model_dump()
    if payload.get("status") not in {"completed", "degraded"}:
        raise OcrServiceError(
            f"OCR service returned non-success status for block "
            f"{request.get('block_id')}: {payload}"
        )

    return payload


def start_ocr_job(
    request: dict,
    ocr_service_url: str = OCR_SERVICE_URL,
    timeout: float = OCR_JOB_HTTP_TIMEOUT_SECONDS,
) -> dict:
    jobs_url = f"{ocr_service_url.rstrip('/')}/ocr/jobs"

    try:
        response = httpx.post(
            jobs_url,
            json=request,
            timeout=timeout,
            trust_env=False,
        )
        response.raise_for_status()
        payload = response.json()
        validated = OcrJobStartResponse.model_validate(payload)
    except httpx.HTTPStatusError as exc:
        raise OcrServiceError(
            f"OCR async job start for block {request.get('block_id')} failed "
            f"with HTTP {exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise OcrServiceError(
            f"OCR async job start failed for block {request.get('block_id')} "
            f"at {jobs_url}: {exc}"
        ) from exc
    except ValueError as exc:
        raise OcrServiceError(
            f"OCR async job start response for block {request.get('block_id')} "
            f"is not valid JSON: {exc}"
        ) from exc

    return validated.model_dump()


def get_ocr_job_status(
    task_id: str,
    ocr_service_url: str = OCR_SERVICE_URL,
    timeout: float = OCR_JOB_HTTP_TIMEOUT_SECONDS,
) -> dict:
    status_url = f"{ocr_service_url.rstrip('/')}/ocr/jobs/{task_id}"

    try:
        response = httpx.get(status_url, timeout=timeout, trust_env=False)
        response.raise_for_status()
        payload = response.json()
        validated = OcrJobStatusResponse.model_validate(payload)
    except httpx.HTTPStatusError as exc:
        raise OcrServiceError(
            f"OCR async job status request for task {task_id} failed with HTTP "
            f"{exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise OcrServiceError(
            f"OCR async job status request failed for task {task_id} "
            f"at {status_url}: {exc}"
        ) from exc
    except ValueError as exc:
        raise OcrServiceError(
            f"OCR async job status response for task {task_id} is not valid JSON: {exc}"
        ) from exc

    return validated.model_dump()


def parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def seconds_since(value: str) -> float:
    heartbeat = parse_iso_datetime(value)
    if heartbeat.tzinfo is None:
        heartbeat = heartbeat.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - heartbeat).total_seconds())


def wait_for_ocr_job(
    task_id: str,
    request: dict,
    ocr_service_url: str = OCR_SERVICE_URL,
    poll_interval: float = OCR_JOB_POLL_INTERVAL_SECONDS,
    stall_timeout: float = OCR_JOB_STALL_TIMEOUT_SECONDS,
    max_runtime: float = OCR_JOB_MAX_RUNTIME_SECONDS,
) -> dict:
    started = perf_counter()

    while True:
        status = get_ocr_job_status(task_id, ocr_service_url)
        state = status["status"]

        if state == "completed":
            return OcrResponse.model_validate(status["result"]).model_dump()

        if state in {"failed", "stalled"}:
            raise OcrServiceError(
                f"OCR async job {task_id} for block {request.get('block_id')} "
                f"ended with status {state}: {status.get('error') or status.get('message')}"
            )

        heartbeat_age = seconds_since(status["last_heartbeat_at"])
        if heartbeat_age > stall_timeout:
            raise OcrServiceError(
                f"OCR async job {task_id} for block {request.get('block_id')} "
                f"appears stalled: last heartbeat was {heartbeat_age:.1f}s ago "
                f"at stage {status.get('stage')}"
            )

        elapsed = perf_counter() - started
        if max_runtime > 0 and elapsed > max_runtime:
            raise OcrServiceError(
                f"OCR async job {task_id} for block {request.get('block_id')} "
                f"exceeded max runtime of {max_runtime:.1f}s"
            )

        sleep(poll_interval)


def call_ocr_block(
    request: dict,
    ocr_service_url: str = OCR_SERVICE_URL,
) -> dict:
    if not OCR_ASYNC_ENABLED:
        return call_ocr_service(request, ocr_service_url)

    job = start_ocr_job(request, ocr_service_url)
    return wait_for_ocr_job(job["task_id"], request, ocr_service_url)


def normalize_ocr_response(raw: dict, request: dict) -> dict:
    raw = OcrResponse.model_validate(raw).model_dump()
    source = raw["model"]["name"]
    return {
        "job_id": raw["job_id"],
        "document_id": raw.get("document_id"),
        "page_number": raw["page_number"],
        "block_id": raw["block_id"],
        "block_type": request["block_type"],
        "layout_label": request.get("layout_label"),
        "content_role": raw["content_role"],
        "recognition_task": raw["recognition_task"],
        "format": raw["format"],
        "content": raw["content"],
        "confidence": raw.get("confidence"),
        "bbox": tuple(request["bbox"]),
        "order": request["order"],
        "image_path": request["image_path"],
        "source": source,
        "warnings": raw.get("warnings", []),
    }


def record_ocr_failure(
    job_id: str,
    paths: dict[str, Path],
    meta: dict,
    trace: dict,
    error: str,
    ocr_service_url: str,
    block_id: str | None = None,
) -> None:
    now = datetime.now(UTC).isoformat()
    details = {
        "error": error,
        "ocr_service_url": ocr_service_url,
    }
    if block_id is not None:
        details["block_id"] = block_id

    meta["status"] = "ocr_failed"
    meta["updated_at"] = now
    meta["stages"].append(
        {
            "name": "ocr",
            "status": "failed",
            "error": error,
            "ocr_service_url": ocr_service_url,
        }
    )

    trace["events"].append(
        {
            "ts": now,
            "stage": "ocr",
            "event": "failed",
            "details": details,
        }
    )

    append_log_line(
        paths["job_dir"] / "logs.jsonl",
        {
            "ts": now,
            "level": "ERROR",
            "stage": "ocr",
            "message": "OCR failed",
            "job_id": job_id,
            **details,
        },
    )
    write_json(paths["job_dir"] / "meta.json", meta)
    write_json(paths["job_dir"] / "trace.json", trace)


def run_ocr_stage(
    job_id: str,
    document_id: str,
    paths: dict[str, Path],
    meta: dict,
    trace: dict,
    layout_asset_pages: list[dict],
    ocr_service_url: str | None = None,
) -> dict:
    started = perf_counter()
    service_url = ocr_service_url or OCR_SERVICE_URL
    ocr_crops = [crop for crop in iter_page_crops(layout_asset_pages) if is_ocr_crop(crop)]
    vision_crops = [crop for crop in iter_page_crops(layout_asset_pages) if is_vision_crop(crop)]
    raw_by_page: dict[int, list[dict]] = {}
    normalized_by_page: dict[int, list[dict]] = {}
    raw_artifacts = []
    normalized_artifacts = []
    warnings: list[str] = []
    sources: set[str] = set()

    try:
        if ocr_crops:
            check_ocr_service_ready(service_url)

        for crop in ocr_crops:
            request = build_ocr_request(
                job_id=job_id,
                document_id=document_id,
                crop=crop,
            )
            raw = call_ocr_block(request, service_url)
            normalized = normalize_ocr_response(raw, request)

            page_number = crop["page_number"]
            raw_by_page.setdefault(page_number, []).append(raw)
            normalized_by_page.setdefault(page_number, []).append(normalized)
            warnings.extend(raw.get("warnings", []))
            sources.add(raw["model"]["name"])

            trace["events"].append(
                {
                    "ts": datetime.now(UTC).isoformat(),
                    "stage": "ocr",
                    "event": "block_completed",
                    "details": {
                        "page_number": page_number,
                        "block_id": crop["block_id"],
                        "recognition_task": request["recognition_task"],
                        "format": raw["format"],
                    },
                }
            )
    except OcrServiceError as exc:
        record_ocr_failure(
            job_id=job_id,
            paths=paths,
            meta=meta,
            trace=trace,
            error=str(exc),
            ocr_service_url=service_url,
            block_id=locals().get("crop", {}).get("block_id"),
        )
        raise
    except Exception as exc:
        error = f"Unexpected OCR stage failure: {exc}"
        record_ocr_failure(
            job_id=job_id,
            paths=paths,
            meta=meta,
            trace=trace,
            error=error,
            ocr_service_url=service_url,
            block_id=locals().get("crop", {}).get("block_id"),
        )
        raise OcrServiceError(error) from exc

    for page_number in sorted(normalized_by_page):
        source = ",".join(sorted(sources)) if sources else "none"
        raw_path = paths["debug_dir"] / f"ocr_raw_page_{page_number:04d}.json"
        normalized_path = paths["debug_dir"] / f"ocr_normalized_page_{page_number:04d}.json"
        artifact = NormalizedOcrArtifact(
            stage="ocr",
            status="completed",
            source=source,
            job_id=job_id,
            document_id=document_id,
            page_number=page_number,
            blocks=normalized_by_page[page_number],
            warnings=warnings,
        )
        write_json(raw_path, {"stage": "ocr", "page_number": page_number, "blocks": raw_by_page[page_number]})
        write_json(normalized_path, artifact.model_dump())
        raw_artifacts.append(str(raw_path.resolve()))
        normalized_artifacts.append(str(normalized_path.resolve()))

    now = datetime.now(UTC).isoformat()
    manifest_path = paths["debug_dir"] / "ocr_manifest.json"
    manifest = {
        "stage": "ocr",
        "status": "completed",
        "job_id": job_id,
        "ocr_service_url": service_url,
        "blocks": len(ocr_crops),
        "vision_pending_blocks": len(vision_crops),
        "artifacts": {
            "raw": raw_artifacts,
            "normalized": normalized_artifacts,
        },
        "service_time_ms": int((perf_counter() - started) * 1000),
    }
    write_json(manifest_path, manifest)

    meta["status"] = "ocr_completed"
    meta["updated_at"] = now
    meta["stages"].append(
        {
            "name": "ocr",
            "status": "completed",
            "blocks": len(ocr_crops),
            "vision_pending_blocks": len(vision_crops),
            "source": ",".join(sorted(sources)) if sources else "none",
            "ocr_service_url": service_url,
            "artifacts": {
                "manifest": str(manifest_path.resolve()),
                "raw": raw_artifacts,
                "normalized": normalized_artifacts,
            },
        }
    )

    trace["events"].append(
        {
            "ts": now,
            "stage": "ocr",
            "event": "completed",
            "details": {
                "blocks": len(ocr_crops),
                "vision_pending_blocks": len(vision_crops),
            },
        }
    )

    append_log_line(
        paths["job_dir"] / "logs.jsonl",
        {
            "ts": now,
            "level": "INFO",
            "stage": "ocr",
            "message": "OCR completed",
            "job_id": job_id,
            "blocks": len(ocr_crops),
            "vision_pending_blocks": len(vision_crops),
            "ocr_service_url": service_url,
        },
    )

    return manifest
