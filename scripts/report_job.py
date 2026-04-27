"""
Print a compact validation report for one pipeline job.

Usage:
    python scripts/report_job.py job-20260427-122837-9a453e
    python scripts/report_job.py C:/project/jobs/output/job-20260427-122837-9a453e
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "jobs" / "output"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_job_dir(job: str, output_dir: Path) -> Path:
    candidate = Path(job)
    if candidate.is_dir():
        return candidate.resolve()

    candidate = output_dir / job
    if candidate.is_dir():
        return candidate.resolve()

    raise FileNotFoundError(
        f"Job folder not found for {job!r}. Checked {Path(job)} and {candidate}."
    )


def iter_layout_artifacts(job_dir: Path) -> list[dict[str, Any]]:
    return [
        read_json(path)
        for path in sorted((job_dir / "debug").glob("layout_normalized_page_*.json"))
    ]


def iter_ocr_artifacts(job_dir: Path) -> list[dict[str, Any]]:
    return [
        read_json(path)
        for path in sorted((job_dir / "debug").glob("ocr_normalized_page_*.json"))
    ]


def format_counter(counter: Counter[str]) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counter.items()))


def print_stage_summary(meta: dict[str, Any]) -> None:
    print("Stages:")
    for stage in meta.get("stages", []):
        details = []
        for key in ("pages", "blocks", "crops", "vision_pending_blocks", "source"):
            if key in stage:
                details.append(f"{key}={stage[key]}")
        detail_text = f" ({', '.join(details)})" if details else ""
        print(f"  - {stage.get('name', 'unknown')}: {stage.get('status', 'unknown')}{detail_text}")


def print_layout_summary(layout_artifacts: list[dict[str, Any]]) -> None:
    type_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()

    print("Layout:")
    if not layout_artifacts:
        print("  no normalized layout artifacts found")
        return

    for artifact in layout_artifacts:
        page_number = artifact["page_number"]
        blocks = artifact.get("blocks", [])
        print(f"  page {page_number}: {len(blocks)} blocks")
        for block in blocks:
            block_type = block.get("type", "unknown")
            layout_label = block.get("layout_label") or "none"
            type_counts[block_type] += 1
            label_counts[layout_label] += 1
            confidence = block.get("confidence")
            confidence_text = f"{confidence:.3f}" if isinstance(confidence, float) else str(confidence)
            print(
                "    "
                f"{block.get('block_id')} order={block.get('order')} "
                f"type={block_type} label={layout_label} conf={confidence_text}"
            )

    print(f"  type summary: {format_counter(type_counts)}")
    print(f"  label summary: {format_counter(label_counts)}")


def print_routing_summary(job_dir: Path) -> None:
    manifest_path = job_dir / "debug" / "layout_assets.json"
    print("Routing:")
    if not manifest_path.is_file():
        print("  layout_assets.json not found")
        return

    manifest = read_json(manifest_path)
    target_counts: Counter[str] = Counter()
    task_counts: Counter[str] = Counter()
    format_counts: Counter[str] = Counter()

    for page in manifest.get("pages", []):
        for crop in page.get("crops", []):
            route = crop.get("routing", {})
            target_counts[route.get("target_service", "unknown")] += 1
            task_counts[route.get("recognition_task", "unknown")] += 1
            format_counts[route.get("requested_format", "unknown")] += 1

    print(f"  targets: {format_counter(target_counts)}")
    print(f"  tasks: {format_counter(task_counts)}")
    print(f"  formats: {format_counter(format_counts)}")
    print(f"  crops manifest: {manifest_path}")


def print_ocr_summary(ocr_artifacts: list[dict[str, Any]]) -> None:
    task_counts: Counter[str] = Counter()
    format_counts: Counter[str] = Counter()

    print("OCR:")
    if not ocr_artifacts:
        print("  no normalized OCR artifacts found")
        return

    for artifact in ocr_artifacts:
        blocks = artifact.get("blocks", [])
        print(f"  page {artifact['page_number']}: {len(blocks)} blocks")
        for block in blocks:
            task_counts[block.get("recognition_task", "unknown")] += 1
            format_counts[block.get("format", "unknown")] += 1

    print(f"  tasks: {format_counter(task_counts)}")
    print(f"  formats: {format_counter(format_counts)}")


def print_vision_summary(job_dir: Path) -> None:
    manifest_path = job_dir / "debug" / "vision_pending_manifest.json"
    print("Vision:")
    if not manifest_path.is_file():
        print("  vision_pending_manifest.json not found")
        return

    manifest = read_json(manifest_path)
    blocks = manifest.get("blocks", [])
    role_counts: Counter[str] = Counter()
    task_counts: Counter[str] = Counter()
    for block in blocks:
        route = block.get("routing", {})
        role_counts[route.get("content_role", "unknown")] += 1
        task_counts[route.get("recognition_task", "unknown")] += 1

    print(f"  status: {manifest.get('status')}")
    print(f"  pending blocks: {manifest.get('block_count', len(blocks))}")
    print(f"  roles: {format_counter(role_counts)}")
    print(f"  tasks: {format_counter(task_counts)}")
    print(f"  manifest: {manifest_path}")


def print_assembly_summary(job_dir: Path) -> None:
    manifest_path = job_dir / "debug" / "assembly_manifest.json"
    print("Assembly:")
    if not manifest_path.is_file():
        print("  assembly_manifest.json not found")
        return

    manifest = read_json(manifest_path)
    print(f"  status: {manifest.get('status')}")
    print(f"  blocks: {manifest.get('blocks', 0)}")
    print(f"  sources: {format_counter(Counter(manifest.get('sources', {})))}")
    print(f"  statuses: {format_counter(Counter(manifest.get('statuses', {})))}")
    print(f"  markdown: {manifest.get('artifacts', {}).get('markdown', job_dir / 'output' / 'article.md')}")
    print(f"  content stream: {manifest.get('artifacts', {}).get('content_stream', job_dir / 'debug' / 'content_stream.json')}")


def print_artifact_paths(job_dir: Path) -> None:
    print("Artifacts:")
    print(f"  pages: {job_dir / 'assets' / 'pages'}")
    print(f"  overlays: {job_dir / 'assets' / 'layout'}")
    print(f"  crops: {job_dir / 'assets' / 'crops'}")
    print(f"  debug: {job_dir / 'debug'}")
    print(f"  output: {job_dir / 'output'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print a validation report for a SCI-OCR job.")
    parser.add_argument("job", help="Job id or path to a jobs/output/<job_id> folder.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Base jobs output folder. Defaults to {DEFAULT_OUTPUT_DIR}.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    job_dir = resolve_job_dir(args.job, args.output_dir)
    meta_path = job_dir / "meta.json"
    if not meta_path.is_file():
        raise FileNotFoundError(f"meta.json not found in {job_dir}")

    meta = read_json(meta_path)
    layout_artifacts = iter_layout_artifacts(job_dir)
    ocr_artifacts = iter_ocr_artifacts(job_dir)

    print(f"Job: {meta.get('job_id', job_dir.name)}")
    print(f"Status: {meta.get('status', 'unknown')}")
    print(f"Input: {meta.get('input', {}).get('filename', 'unknown')}")
    print(f"Folder: {job_dir}")
    print()

    print_stage_summary(meta)
    print()
    print_layout_summary(layout_artifacts)
    print()
    print_routing_summary(job_dir)
    print()
    print_ocr_summary(ocr_artifacts)
    print()
    print_vision_summary(job_dir)
    print()
    print_assembly_summary(job_dir)
    print()
    print_artifact_paths(job_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
