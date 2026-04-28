"""
HTTP-backed vision stage.

The orchestrator sends image/chart crops to an optional external vision worker.
If the worker is not configured or unavailable, visual crops remain pending and
assembly inserts placeholders as before.
"""

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import httpx

from orchestrator.app.config import VISION_SERVICE_URL, VISION_TIMEOUT_SECONDS
from orchestrator.app.job_metadata import append_log_line, write_json
from shared.contracts.vision import (
    NormalizedVisionArtifact,
    VisionReadyResponse,
    VisionRequest,
    VisionResponse,
)


class VisionServiceError(RuntimeError):
    """Raised when the external vision service cannot complete a request."""


def _route(crop: dict) -> dict:
    return crop.get("routing", {})


def is_vision_crop(crop: dict) -> bool:
    return _route(crop).get("target_service") == "vision"


def iter_page_crops(layout_asset_pages: list[dict]):
    for page in layout_asset_pages:
        for crop in page.get("crops", []):
            yield crop


def build_vision_request(
    job_id: str,
    document_id: str,
    crop: dict,
) -> dict:
    route = _route(crop)
    request = VisionRequest(
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


def check_vision_service_ready(
    vision_service_url: str,
    timeout: float = VISION_TIMEOUT_SECONDS,
) -> dict:
    ready_url = f"{vision_service_url.rstrip('/')}/ready"

    try:
        response = httpx.get(ready_url, timeout=timeout, trust_env=False)
        response.raise_for_status()
        payload = response.json()
        ready = VisionReadyResponse.model_validate(payload)
    except httpx.HTTPStatusError as exc:
        raise VisionServiceError(
            f"Vision service readiness check failed with HTTP "
            f"{exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise VisionServiceError(
            f"Vision service is not reachable at {ready_url}: {exc}"
        ) from exc
    except ValueError as exc:
        raise VisionServiceError(
            f"Vision service readiness response is not valid JSON: {exc}"
        ) from exc

    return ready.model_dump()


def call_vision_service(
    request: dict,
    vision_service_url: str,
    timeout: float = VISION_TIMEOUT_SECONDS,
) -> dict:
    vision_url = f"{vision_service_url.rstrip('/')}/vision"

    try:
        response = httpx.post(
            vision_url,
            json=request,
            timeout=timeout,
            trust_env=False,
        )
        response.raise_for_status()
        payload = response.json()
        validated = VisionResponse.model_validate(payload)
    except httpx.HTTPStatusError as exc:
        raise VisionServiceError(
            f"Vision request for block {request.get('block_id')} failed "
            f"with HTTP {exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise VisionServiceError(
            f"Vision service request failed for block {request.get('block_id')} "
            f"at {vision_url}: {exc}"
        ) from exc
    except ValueError as exc:
        raise VisionServiceError(
            f"Vision service response for block {request.get('block_id')} "
            f"is not valid JSON: {exc}"
        ) from exc

    payload = validated.model_dump()
    if payload.get("status") not in {"completed", "degraded"}:
        raise VisionServiceError(
            f"Vision service returned non-success status for block "
            f"{request.get('block_id')}: {payload}"
        )
    return payload


def normalize_vision_response(raw: dict, request: dict) -> dict:
    raw = VisionResponse.model_validate(raw).model_dump()
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
        "visual_type": raw["visual_type"],
        "format": raw["format"],
        "content": raw["content"],
        "structured_data": raw.get("structured_data", {}),
        "confidence": raw.get("confidence"),
        "bbox": tuple(request["bbox"]),
        "order": request["order"],
        "image_path": request["image_path"],
        "source": source,
        "warnings": raw.get("warnings", []),
    }


def write_vision_pending_manifest(
    job_id: str,
    paths: dict[str, Path],
    vision_crops: list[dict],
    reason: str,
    status: str = "pending",
) -> str:
    manifest_path = paths["debug_dir"] / "vision_pending_manifest.json"
    manifest = {
        "stage": "vision",
        "status": status,
        "job_id": job_id,
        "blocks": vision_crops,
        "block_count": len(vision_crops),
        "reason": reason,
    }
    write_json(manifest_path, manifest)
    return str(manifest_path.resolve())


def record_pending_stage(
    job_id: str,
    paths: dict[str, Path],
    meta: dict,
    trace: dict,
    vision_crops: list[dict],
    reason: str,
) -> dict:
    now = datetime.now(UTC).isoformat()
    pending_blocks = [{**crop, "status": "pending"} for crop in vision_crops]
    pending_path = write_vision_pending_manifest(
        job_id=job_id,
        paths=paths,
        vision_crops=pending_blocks,
        reason=reason,
        status="pending",
    )

    meta["status"] = "vision_pending"
    meta["updated_at"] = now
    meta["stages"].append(
        {
            "name": "vision",
            "status": "pending",
            "blocks": len(pending_blocks),
            "reason": reason,
            "artifacts": {
                "manifest": pending_path,
            },
        }
    )
    trace["events"].append(
        {
            "ts": now,
            "stage": "vision",
            "event": "pending_manifest_written",
            "details": {
                "blocks": len(pending_blocks),
                "reason": reason,
            },
        }
    )
    append_log_line(
        paths["job_dir"] / "logs.jsonl",
        {
            "ts": now,
            "level": "INFO",
            "stage": "vision",
            "message": "Vision blocks left pending",
            "job_id": job_id,
            "blocks": len(pending_blocks),
            "reason": reason,
        },
    )
    return {
        "stage": "vision",
        "status": "pending",
        "blocks": len(pending_blocks),
        "artifacts": {"pending": pending_path},
    }


def run_vision_stage(
    job_id: str,
    document_id: str,
    paths: dict[str, Path],
    meta: dict,
    trace: dict,
    layout_asset_pages: list[dict],
    vision_service_url: str | None = None,
) -> dict:
    started = perf_counter()
    service_url = vision_service_url if vision_service_url is not None else VISION_SERVICE_URL
    vision_crops = [crop for crop in iter_page_crops(layout_asset_pages) if is_vision_crop(crop)]

    if not service_url:
        return record_pending_stage(
            job_id=job_id,
            paths=paths,
            meta=meta,
            trace=trace,
            vision_crops=vision_crops,
            reason="vision service is not configured",
        )

    raw_by_page: dict[int, list[dict]] = {}
    normalized_by_page: dict[int, list[dict]] = {}
    raw_artifacts = []
    normalized_artifacts = []
    warnings: list[str] = []
    sources: set[str] = set()

    try:
        if vision_crops:
            check_vision_service_ready(service_url)

        for crop in vision_crops:
            request = build_vision_request(
                job_id=job_id,
                document_id=document_id,
                crop=crop,
            )
            raw = call_vision_service(request, service_url)
            normalized = normalize_vision_response(raw, request)

            page_number = crop["page_number"]
            raw_by_page.setdefault(page_number, []).append(raw)
            normalized_by_page.setdefault(page_number, []).append(normalized)
            warnings.extend(raw.get("warnings", []))
            sources.add(raw["model"]["name"])

            trace["events"].append(
                {
                    "ts": datetime.now(UTC).isoformat(),
                    "stage": "vision",
                    "event": "block_completed",
                    "details": {
                        "page_number": page_number,
                        "block_id": crop["block_id"],
                        "recognition_task": request["recognition_task"],
                        "visual_type": raw["visual_type"],
                    },
                }
            )
    except VisionServiceError as exc:
        return record_pending_stage(
            job_id=job_id,
            paths=paths,
            meta=meta,
            trace=trace,
            vision_crops=vision_crops,
            reason=str(exc),
        )

    for page_number in sorted(normalized_by_page):
        source = ",".join(sorted(sources)) if sources else "none"
        raw_path = paths["debug_dir"] / f"vision_raw_page_{page_number:04d}.json"
        normalized_path = paths["debug_dir"] / f"vision_normalized_page_{page_number:04d}.json"
        artifact = NormalizedVisionArtifact(
            stage="vision",
            status="completed",
            source=source,
            job_id=job_id,
            document_id=document_id,
            page_number=page_number,
            blocks=normalized_by_page[page_number],
            warnings=warnings,
        )
        write_json(
            raw_path,
            {"stage": "vision", "page_number": page_number, "blocks": raw_by_page[page_number]},
        )
        write_json(normalized_path, artifact.model_dump())
        raw_artifacts.append(str(raw_path.resolve()))
        normalized_artifacts.append(str(normalized_path.resolve()))

    pending_path = write_vision_pending_manifest(
        job_id=job_id,
        paths=paths,
        vision_crops=[],
        reason="vision service completed all routed visual blocks",
        status="completed",
    )

    now = datetime.now(UTC).isoformat()
    manifest_path = paths["debug_dir"] / "vision_manifest.json"
    manifest = {
        "stage": "vision",
        "status": "completed",
        "job_id": job_id,
        "vision_service_url": service_url,
        "blocks": len(vision_crops),
        "pending_blocks": 0,
        "artifacts": {
            "raw": raw_artifacts,
            "normalized": normalized_artifacts,
            "pending": pending_path,
        },
        "service_time_ms": int((perf_counter() - started) * 1000),
    }
    write_json(manifest_path, manifest)

    meta["status"] = "vision_completed"
    meta["updated_at"] = now
    meta["stages"].append(
        {
            "name": "vision",
            "status": "completed",
            "blocks": len(vision_crops),
            "pending_blocks": 0,
            "source": ",".join(sorted(sources)) if sources else "none",
            "vision_service_url": service_url,
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
            "stage": "vision",
            "event": "completed",
            "details": {
                "blocks": len(vision_crops),
                "pending_blocks": 0,
            },
        }
    )
    append_log_line(
        paths["job_dir"] / "logs.jsonl",
        {
            "ts": now,
            "level": "INFO",
            "stage": "vision",
            "message": "Vision completed",
            "job_id": job_id,
            "blocks": len(vision_crops),
            "vision_service_url": service_url,
        },
    )
    return manifest
