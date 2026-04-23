"""
Service-shaped layout stage stub.

This module keeps the orchestrator aligned with the future external layout
service contract while the real page renderer and PP-DocLayoutV3 backend are
not connected yet.
"""

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from orchestrator.app.job_metadata import append_log_line, write_json


LAYOUT_STUB_VERSION = "0.1.0"


def build_layout_request(
    job_id: str,
    document_id: str,
    page_number: int,
    image_path: Path,
) -> dict:
    """
    Build the request shape expected by the future HTTP layout service.
    """
    return {
        "job_id": job_id,
        "document_id": document_id,
        "page_number": page_number,
        "image_path": str(image_path.resolve()),
    }


def call_layout_stub(request: dict) -> dict:
    """
    Return a deterministic service-shaped layout response.

    The page dimensions are read from the rendered PNG, but block detection is
    still deterministic until the real layout backend is connected.
    """
    started = perf_counter()
    page_number = request["page_number"]

    image_width, image_height = read_png_dimensions(Path(request["image_path"]))

    response = {
        "status": "completed",
        "job_id": request["job_id"],
        "document_id": request.get("document_id"),
        "page_number": page_number,
        "model": {
            "name": "layout_stub",
            "version": LAYOUT_STUB_VERSION,
        },
        "image": {
            "path": request["image_path"],
            "width": image_width,
            "height": image_height,
        },
        "blocks": [
            {
                "block_id": f"p{page_number}_b1",
                "type": "text",
                "bbox": [100, 100, 700, 180],
                "confidence": 0.98,
                "order": 1,
            }
        ],
        "warnings": [
            "layout_stub did not infer blocks from image content because the real layout backend is not connected yet"
        ],
        "error": None,
    }

    response["service_time_ms"] = int((perf_counter() - started) * 1000)
    return response


def read_png_dimensions(image_path: Path) -> tuple[int, int]:
    """
    Read rendered page dimensions for the local stub response.
    """
    try:
        import fitz

        pixmap = fitz.Pixmap(str(image_path))
        return pixmap.width, pixmap.height
    except Exception:
        return 1000, 1400


def normalize_layout_response(raw: dict) -> dict:
    """
    Convert service output into the canonical layout format.
    """
    source = raw["model"]["name"]

    return {
        "stage": "layout",
        "status": raw["status"],
        "source": source,
        "job_id": raw["job_id"],
        "document_id": raw.get("document_id"),
        "page_number": raw["page_number"],
        "image": raw["image"],
        "blocks": [
            {
                **block,
                "source": source,
            }
            for block in raw["blocks"]
        ],
        "warnings": raw.get("warnings", []),
    }


def run_layout_stage(
    job_id: str,
    copied_file: Path,
    paths: dict[str, Path],
    meta: dict,
    trace: dict,
    rendered_pages: list[dict],
) -> None:
    """
    Run the stub-compatible layout stage and persist per-page artifacts.
    """
    raw_artifacts = []
    normalized_artifacts = []
    total_blocks = 0

    for rendered_page in rendered_pages:
        page_number = rendered_page["page_number"]
        page_image_path = Path(rendered_page["image_path"])

        request = build_layout_request(
            job_id=job_id,
            document_id=copied_file.name,
            page_number=page_number,
            image_path=page_image_path,
        )
        raw = call_layout_stub(request)
        normalized = normalize_layout_response(raw)

        page_suffix = f"page_{page_number:04d}"
        raw_path = paths["debug_dir"] / f"layout_raw_{page_suffix}.json"
        normalized_path = paths["debug_dir"] / f"layout_normalized_{page_suffix}.json"
        write_json(raw_path, raw)
        write_json(normalized_path, normalized)

        block_count = len(normalized["blocks"])
        total_blocks += block_count
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

    now = datetime.now(UTC).isoformat()

    meta["status"] = "layout_completed"
    meta["updated_at"] = now
    meta["stages"].append(
        {
            "name": "layout",
            "status": "completed",
            "pages": len(rendered_pages),
            "blocks": total_blocks,
            "source": "layout_stub",
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
        },
    )
