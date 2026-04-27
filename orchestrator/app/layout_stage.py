"""
HTTP-backed layout stage.

The orchestrator owns artifact persistence and normalization, while layout
detection is delegated to an external service behind a stable HTTP contract.
"""

from datetime import UTC, datetime
from pathlib import Path

import httpx

from orchestrator.app.config import LAYOUT_SERVICE_URL
from orchestrator.app.job_metadata import append_log_line, write_json
from shared.contracts.layout import (
    LayoutReadyResponse,
    LayoutRequest,
    LayoutResponse,
    NormalizedLayoutArtifact,
)


LAYOUT_TIMEOUT_SECONDS = 10.0


class LayoutServiceError(RuntimeError):
    """Raised when the external layout service cannot complete a request."""


def build_layout_request(
    job_id: str,
    document_id: str,
    page_number: int,
    image_path: Path,
) -> dict:
    """
    Build the request shape expected by the future HTTP layout service.
    """
    request = LayoutRequest(
        job_id=job_id,
        document_id=document_id,
        page_number=page_number,
        image_path=str(image_path.resolve()),
    )
    return request.model_dump()


def check_layout_service_ready(
    layout_service_url: str = LAYOUT_SERVICE_URL,
    timeout: float = LAYOUT_TIMEOUT_SECONDS,
) -> dict:
    """
    Verify that the layout backend is reachable before sending page requests.
    """
    ready_url = f"{layout_service_url.rstrip('/')}/ready"

    try:
        response = httpx.get(ready_url, timeout=timeout, trust_env=False)
        response.raise_for_status()
        payload = response.json()
        ready = LayoutReadyResponse.model_validate(payload)
    except httpx.HTTPStatusError as exc:
        raise LayoutServiceError(
            f"Layout service readiness check failed with HTTP "
            f"{exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise LayoutServiceError(
            f"Layout service is not reachable at {ready_url}: {exc}"
        ) from exc
    except ValueError as exc:
        raise LayoutServiceError(
            f"Layout service readiness response is not valid JSON: {exc}"
        ) from exc

    return ready.model_dump()


def call_layout_service(
    request: dict,
    layout_service_url: str = LAYOUT_SERVICE_URL,
    timeout: float = LAYOUT_TIMEOUT_SECONDS,
) -> dict:
    """
    Send one rendered page to the external layout service.
    """
    layout_url = f"{layout_service_url.rstrip('/')}/layout"

    try:
        response = httpx.post(
            layout_url,
            json=request,
            timeout=timeout,
            trust_env=False,
        )
        response.raise_for_status()
        payload = response.json()
        validated = LayoutResponse.model_validate(payload)
    except httpx.HTTPStatusError as exc:
        raise LayoutServiceError(
            f"Layout request for page {request.get('page_number')} failed "
            f"with HTTP {exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise LayoutServiceError(
            f"Layout service request failed for page "
            f"{request.get('page_number')} at {layout_url}: {exc}"
        ) from exc
    except ValueError as exc:
        raise LayoutServiceError(
            f"Layout service response for page {request.get('page_number')} "
            f"is not valid JSON: {exc}"
        ) from exc

    payload = validated.model_dump()

    if payload.get("status") not in {"completed", "degraded"}:
        raise LayoutServiceError(
            f"Layout service returned non-success status for page "
            f"{request.get('page_number')}: {payload}"
        )

    return payload


def normalize_layout_response(raw: dict) -> dict:
    """
    Convert service output into the canonical layout format.
    """
    raw = LayoutResponse.model_validate(raw).model_dump()
    source = raw["model"]["name"]

    normalized = NormalizedLayoutArtifact(
        stage="layout",
        status=raw["status"],
        source=source,
        job_id=raw["job_id"],
        document_id=raw.get("document_id"),
        page_number=raw["page_number"],
        image=raw["image"],
        blocks=[
            {
                **block,
                "source": source,
            }
            for block in raw["blocks"]
        ],
        warnings=raw.get("warnings", []),
    )
    return normalized.model_dump()


def record_layout_failure(
    job_id: str,
    paths: dict[str, Path],
    meta: dict,
    trace: dict,
    error: str,
    layout_service_url: str,
    page_number: int | None = None,
) -> None:
    """
    Persist layout failures before the pipeline raises back to the API layer.
    """
    now = datetime.now(UTC).isoformat()
    details = {
        "error": error,
        "layout_service_url": layout_service_url,
    }
    if page_number is not None:
        details["page_number"] = page_number

    meta["status"] = "layout_failed"
    meta["updated_at"] = now
    meta["stages"].append(
        {
            "name": "layout",
            "status": "failed",
            "error": error,
            "layout_service_url": layout_service_url,
        }
    )

    trace["events"].append(
        {
            "ts": now,
            "stage": "layout",
            "event": "failed",
            "details": details,
        }
    )

    append_log_line(
        paths["job_dir"] / "logs.jsonl",
        {
            "ts": now,
            "level": "ERROR",
            "stage": "layout",
            "message": "Layout failed",
            "job_id": job_id,
            **details,
        },
    )
    write_json(paths["job_dir"] / "meta.json", meta)
    write_json(paths["job_dir"] / "trace.json", trace)


def run_layout_stage(
    job_id: str,
    copied_file: Path,
    paths: dict[str, Path],
    meta: dict,
    trace: dict,
    rendered_pages: list[dict],
    layout_service_url: str | None = None,
) -> list[str]:
    """
    Run the external layout stage and persist per-page artifacts.
    """
    service_url = layout_service_url or LAYOUT_SERVICE_URL
    raw_artifacts = []
    normalized_artifacts = []
    total_blocks = 0
    sources: set[str] = set()

    try:
        check_layout_service_ready(service_url)

        for rendered_page in rendered_pages:
            page_number = rendered_page["page_number"]
            page_image_path = Path(rendered_page["image_path"])

            request = build_layout_request(
                job_id=job_id,
                document_id=copied_file.name,
                page_number=page_number,
                image_path=page_image_path,
            )
            raw = call_layout_service(request, service_url)
            normalized = normalize_layout_response(raw)

            page_suffix = f"page_{page_number:04d}"
            raw_path = paths["debug_dir"] / f"layout_raw_{page_suffix}.json"
            normalized_path = paths["debug_dir"] / f"layout_normalized_{page_suffix}.json"
            write_json(raw_path, raw)
            write_json(normalized_path, normalized)

            block_count = len(normalized["blocks"])
            total_blocks += block_count
            sources.add(normalized["source"])
            raw_artifacts.append(str(raw_path.resolve()))
            normalized_artifacts.append(str(normalized_path.resolve()))

            trace["events"].append(
                {
                    "ts": datetime.now(UTC).isoformat(),
                    "stage": "layout",
                    "event": "page_completed",
                    "details": {
                        "page_number": page_number,
                        "blocks": block_count,
                        "source": normalized["source"],
                    },
                }
            )
    except LayoutServiceError as exc:
        record_layout_failure(
            job_id=job_id,
            paths=paths,
            meta=meta,
            trace=trace,
            error=str(exc),
            layout_service_url=service_url,
            page_number=locals().get("page_number"),
        )
        raise
    except Exception as exc:
        error = f"Unexpected layout stage failure: {exc}"
        record_layout_failure(
            job_id=job_id,
            paths=paths,
            meta=meta,
            trace=trace,
            error=error,
            layout_service_url=service_url,
            page_number=locals().get("page_number"),
        )
        raise LayoutServiceError(error) from exc

    now = datetime.now(UTC).isoformat()
    source = ",".join(sorted(sources)) if sources else "unknown"

    meta["status"] = "layout_completed"
    meta["updated_at"] = now
    meta["stages"].append(
        {
            "name": "layout",
            "status": "completed",
            "pages": len(rendered_pages),
            "blocks": total_blocks,
            "source": source,
            "layout_service_url": service_url,
            "artifacts": {
                "raw": raw_artifacts,
                "normalized": normalized_artifacts,
            },
        }
    )

    append_log_line(
        paths["job_dir"] / "logs.jsonl",
        {
            "ts": now,
            "level": "INFO",
            "stage": "layout",
            "message": "Layout completed",
            "job_id": job_id,
            "pages": len(rendered_pages),
            "blocks": total_blocks,
            "source": source,
            "layout_service_url": service_url,
        },
    )

    return normalized_artifacts
