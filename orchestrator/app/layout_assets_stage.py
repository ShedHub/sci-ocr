"""
Create visual and crop artifacts from normalized layout output.

The layout backend only detects blocks. The orchestrator owns downstream
artifacts such as crops for OCR and human-readable layout overlays.
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from PIL import Image, ImageDraw, ImageFont

from orchestrator.app.job_metadata import append_log_line, write_json


CROPPABLE_BLOCK_TYPES = {"title", "text"}
BLOCK_COLORS = {
    "title": "#e11d48",
    "text": "#2563eb",
    "table": "#16a34a",
    "formula": "#9333ea",
    "figure": "#ea580c",
}


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")
    return cleaned or "block"


def clamp_bbox(bbox: list[float], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    left = max(0, min(width, int(round(x1))))
    top = max(0, min(height, int(round(y1))))
    right = max(0, min(width, int(round(x2))))
    bottom = max(0, min(height, int(round(y2))))
    if right <= left or bottom <= top:
        raise ValueError(f"Invalid bbox after clamping: {bbox}")
    return left, top, right, bottom


def draw_block_label(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    color: str,
) -> None:
    font = ImageFont.load_default()
    left, top, _, _ = box
    text_bbox = draw.textbbox((left, top), label, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    label_top = max(0, top - text_height - 6)
    background = (left, label_top, left + text_width + 8, label_top + text_height + 6)
    draw.rectangle(background, fill=color)
    draw.text((left + 4, label_top + 3), label, fill="white", font=font)


def create_page_layout_assets(
    normalized_layout: dict,
    page_image_path: Path,
    paths: dict[str, Path],
) -> dict:
    page_number = normalized_layout["page_number"]
    page_name = f"page_{page_number:04d}"
    page_crops_dir = paths["crops_dir"] / page_name
    page_crops_dir.mkdir(parents=True, exist_ok=True)

    crop_artifacts = []
    with Image.open(page_image_path) as source_image:
        source = source_image.convert("RGB")
        overlay = source.copy()
        draw = ImageDraw.Draw(overlay)

        for block in normalized_layout["blocks"]:
            block_type = block["type"]
            color = BLOCK_COLORS.get(block_type, "#111827")
            box = clamp_bbox(block["bbox"], source.width, source.height)
            draw.rectangle(box, outline=color, width=4)
            draw_block_label(
                draw=draw,
                box=box,
                label=f"{block['order']} {block_type}",
                color=color,
            )

            if block_type not in CROPPABLE_BLOCK_TYPES:
                continue

            crop_filename = f"{safe_filename(block['block_id'])}.png"
            crop_path = page_crops_dir / crop_filename
            source.crop(box).save(crop_path)
            crop_artifacts.append(
                {
                    "page_number": page_number,
                    "block_id": block["block_id"],
                    "type": block_type,
                    "bbox": list(box),
                    "image_path": str(crop_path.resolve()),
                }
            )

        overlay_path = paths["layout_dir"] / f"{page_name}_layout.png"
        overlay.save(overlay_path)

    return {
        "page_number": page_number,
        "overlay_path": str(overlay_path.resolve()),
        "crops": crop_artifacts,
        "blocks": len(normalized_layout["blocks"]),
    }


def run_layout_assets_stage(
    job_id: str,
    paths: dict[str, Path],
    meta: dict,
    trace: dict,
    normalized_artifact_paths: list[str],
) -> list[dict]:
    started = perf_counter()
    page_artifacts = []

    for artifact_path in normalized_artifact_paths:
        normalized_path = Path(artifact_path)
        normalized_layout = json.loads(normalized_path.read_text(encoding="utf-8"))
        page_image_path = Path(normalized_layout["image"]["path"])
        page_artifacts.append(
            create_page_layout_assets(
                normalized_layout=normalized_layout,
                page_image_path=page_image_path,
                paths=paths,
            )
        )

    now = datetime.now(UTC).isoformat()
    crop_count = sum(len(page["crops"]) for page in page_artifacts)
    block_count = sum(page["blocks"] for page in page_artifacts)
    manifest_path = paths["debug_dir"] / "layout_assets.json"
    manifest = {
        "stage": "layout_assets",
        "status": "completed",
        "job_id": job_id,
        "pages": page_artifacts,
        "blocks": block_count,
        "crops": crop_count,
        "service_time_ms": int((perf_counter() - started) * 1000),
    }
    write_json(manifest_path, manifest)

    meta["status"] = "layout_assets_completed"
    meta["updated_at"] = now
    meta["stages"].append(
        {
            "name": "layout_assets",
            "status": "completed",
            "pages": len(page_artifacts),
            "blocks": block_count,
            "crops": crop_count,
            "artifacts": {
                "manifest": str(manifest_path.resolve()),
                "crops_dir": str(paths["crops_dir"].resolve()),
                "layout_dir": str(paths["layout_dir"].resolve()),
                "overlays": [page["overlay_path"] for page in page_artifacts],
            },
        }
    )

    trace["events"].append(
        {
            "ts": now,
            "stage": "layout_assets",
            "event": "assets_created",
            "details": {
                "pages": len(page_artifacts),
                "blocks": block_count,
                "crops": crop_count,
            },
        }
    )

    append_log_line(
        paths["job_dir"] / "logs.jsonl",
        {
            "ts": now,
            "level": "INFO",
            "stage": "layout_assets",
            "message": "Layout crop and overlay assets created",
            "job_id": job_id,
            "pages": len(page_artifacts),
            "blocks": block_count,
            "crops": crop_count,
        },
    )

    return page_artifacts
