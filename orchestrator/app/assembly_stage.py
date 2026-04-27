"""
Assemble normalized pipeline artifacts into LLM-ready Markdown.

The assembly stage is deterministic. It does not call models or mutate upstream
artifacts; it reads normalized layout, OCR output, and pending vision records,
then builds a linear content stream in article reading order.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from orchestrator.app.job_metadata import append_log_line, write_json


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sort_key(entry: dict[str, Any]) -> tuple[int, int, float, float, str]:
    bbox = entry.get("bbox") or [0, 0, 0, 0]
    return (
        int(entry.get("page_number", 0)),
        int(entry.get("order", 0)),
        float(bbox[1]),
        float(bbox[0]),
        str(entry.get("block_id", "")),
    )


def load_layout_blocks(paths: dict[str, Path]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for artifact_path in sorted(paths["debug_dir"].glob("layout_normalized_page_*.json")):
        artifact = read_json(artifact_path)
        for block in artifact.get("blocks", []):
            blocks.append(
                {
                    **block,
                    "page_number": artifact["page_number"],
                    "document_id": artifact.get("document_id"),
                }
            )
    return blocks


def load_ocr_blocks(paths: dict[str, Path]) -> dict[tuple[int, str], dict[str, Any]]:
    ocr_blocks: dict[tuple[int, str], dict[str, Any]] = {}
    for artifact_path in sorted(paths["debug_dir"].glob("ocr_normalized_page_*.json")):
        artifact = read_json(artifact_path)
        for block in artifact.get("blocks", []):
            ocr_blocks[(block["page_number"], block["block_id"])] = block
    return ocr_blocks


def load_crop_blocks(paths: dict[str, Path]) -> dict[tuple[int, str], dict[str, Any]]:
    manifest_path = paths["debug_dir"] / "layout_assets.json"
    if not manifest_path.is_file():
        return {}

    crop_blocks: dict[tuple[int, str], dict[str, Any]] = {}
    manifest = read_json(manifest_path)
    for page in manifest.get("pages", []):
        for crop in page.get("crops", []):
            crop_blocks[(crop["page_number"], crop["block_id"])] = crop
    return crop_blocks


def load_vision_pending_blocks(paths: dict[str, Path]) -> dict[tuple[int, str], dict[str, Any]]:
    manifest_path = paths["debug_dir"] / "vision_pending_manifest.json"
    if not manifest_path.is_file():
        return {}

    pending_blocks: dict[tuple[int, str], dict[str, Any]] = {}
    manifest = read_json(manifest_path)
    for block in manifest.get("blocks", []):
        pending_blocks[(block["page_number"], block["block_id"])] = block
    return pending_blocks


def infer_kind(layout_block: dict[str, Any], route: dict[str, Any]) -> str:
    task = route.get("recognition_task")
    if task and task != "none":
        return task
    return layout_block.get("type", "unknown")


def build_pending_content(block_id: str, role: str, kind: str) -> str:
    label = "Chart" if kind == "chart" or role == "chart" else "Image"
    return f"[{label} pending: {block_id}]"


def build_missing_ocr_content(block_id: str) -> str:
    return f"[OCR missing: {block_id}]"


def build_content_stream(paths: dict[str, Path]) -> tuple[list[dict[str, Any]], list[str]]:
    layout_blocks = load_layout_blocks(paths)
    ocr_blocks = load_ocr_blocks(paths)
    crop_blocks = load_crop_blocks(paths)
    pending_vision = load_vision_pending_blocks(paths)
    stream: list[dict[str, Any]] = []
    warnings: list[str] = []

    for layout_block in sorted(layout_blocks, key=sort_key):
        key = (layout_block["page_number"], layout_block["block_id"])
        crop = crop_blocks.get(key, {})
        route = crop.get("routing", {})
        target_service = route.get("target_service")
        role = route.get("content_role") or layout_block.get("type", "unknown")
        kind = infer_kind(layout_block, route)
        image_path = crop.get("image_path")
        ocr_block = ocr_blocks.get(key)

        entry = {
            "page_number": layout_block["page_number"],
            "order": layout_block["order"],
            "block_id": layout_block["block_id"],
            "block_type": layout_block["type"],
            "layout_label": layout_block.get("layout_label"),
            "role": role,
            "kind": kind,
            "bbox": layout_block["bbox"],
            "image_path": image_path,
            "target_service": target_service or "unknown",
        }

        if ocr_block is not None:
            stream.append(
                {
                    **entry,
                    "status": "completed",
                    "source": ocr_block.get("source", "ocr"),
                    "format": ocr_block.get("format"),
                    "content": ocr_block.get("content", ""),
                    "warnings": ocr_block.get("warnings", []),
                }
            )
            continue

        if key in pending_vision or target_service == "vision":
            stream.append(
                {
                    **entry,
                    "status": "pending",
                    "source": "vision_pending",
                    "format": "markdown",
                    "content": build_pending_content(layout_block["block_id"], role, kind),
                    "warnings": ["vision service is not implemented yet"],
                }
            )
            continue

        warning = f"Missing OCR output for block {layout_block['block_id']}"
        warnings.append(warning)
        stream.append(
            {
                **entry,
                "status": "missing",
                "source": "assembly",
                "format": "markdown",
                "content": build_missing_ocr_content(layout_block["block_id"]),
                "warnings": [warning],
            }
        )

    return stream, warnings


def normalize_markdown_text(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.strip().splitlines()).strip()


def strip_heading_prefix(value: str) -> str:
    text = normalize_markdown_text(value)
    while text.startswith("#"):
        text = text[1:].lstrip()
    return text


def render_stream_entry(entry: dict[str, Any]) -> str:
    content = normalize_markdown_text(entry.get("content", ""))
    role = entry.get("role")
    kind = entry.get("kind")

    if not content:
        return ""

    if role == "title":
        return f"# {strip_heading_prefix(content)}"

    if role in {"heading", "abstract"}:
        heading_text = strip_heading_prefix(content)
        if role == "abstract" and heading_text.lower() != "abstract":
            return f"## Abstract\n\n{content}"
        return f"## {heading_text}"

    if kind == "formula":
        if role == "inline_formula":
            return f"${content}$"
        return f"$$\n{content}\n$$"

    if kind == "table":
        return content

    if entry.get("source") == "vision_pending":
        return f"> {content}"

    if role in {"caption", "figure_title"}:
        return f"*{content}*"

    return content


def render_markdown(stream: list[dict[str, Any]]) -> str:
    sections: list[str] = []
    current_page: int | None = None

    for entry in stream:
        page_number = entry["page_number"]
        if current_page is None:
            current_page = page_number
        elif page_number != current_page:
            sections.append(f"<!-- page {page_number} -->")
            current_page = page_number

        rendered = render_stream_entry(entry)
        if rendered:
            sections.append(rendered)

    return "\n\n".join(sections).strip() + "\n"


def run_assembly_stage(
    job_id: str,
    paths: dict[str, Path],
    meta: dict,
    trace: dict,
) -> dict[str, Any]:
    started = perf_counter()
    stream, warnings = build_content_stream(paths)
    markdown = render_markdown(stream)

    content_stream_path = paths["debug_dir"] / "content_stream.json"
    manifest_path = paths["debug_dir"] / "assembly_manifest.json"
    article_path = paths["output_dir"] / "article.md"

    write_json(content_stream_path, {"stage": "assembly", "job_id": job_id, "blocks": stream})
    article_path.write_text(markdown, encoding="utf-8")

    source_counts = Counter(entry.get("source", "unknown") for entry in stream)
    role_counts = Counter(entry.get("role", "unknown") for entry in stream)
    status_counts = Counter(entry.get("status", "unknown") for entry in stream)
    now = datetime.now(UTC).isoformat()
    manifest = {
        "stage": "assembly",
        "status": "completed",
        "job_id": job_id,
        "blocks": len(stream),
        "sources": dict(sorted(source_counts.items())),
        "roles": dict(sorted(role_counts.items())),
        "statuses": dict(sorted(status_counts.items())),
        "warnings": warnings,
        "artifacts": {
            "markdown": str(article_path.resolve()),
            "content_stream": str(content_stream_path.resolve()),
        },
        "service_time_ms": int((perf_counter() - started) * 1000),
    }
    write_json(manifest_path, manifest)

    meta["status"] = "assembly_completed"
    meta["updated_at"] = now
    meta["stages"].append(
        {
            "name": "assembly",
            "status": "completed",
            "blocks": len(stream),
            "sources": dict(sorted(source_counts.items())),
            "warnings": len(warnings),
            "artifacts": {
                "manifest": str(manifest_path.resolve()),
                "markdown": str(article_path.resolve()),
                "content_stream": str(content_stream_path.resolve()),
            },
        }
    )

    trace["events"].append(
        {
            "ts": now,
            "stage": "assembly",
            "event": "completed",
            "details": {
                "blocks": len(stream),
                "markdown": str(article_path.resolve()),
            },
        }
    )

    append_log_line(
        paths["job_dir"] / "logs.jsonl",
        {
            "ts": now,
            "level": "INFO",
            "stage": "assembly",
            "message": "Markdown article assembled",
            "job_id": job_id,
            "blocks": len(stream),
            "markdown": str(article_path.resolve()),
        },
    )

    return manifest
