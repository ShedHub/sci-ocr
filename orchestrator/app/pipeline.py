# pipeline.py
"""
Pipeline entry point.

This module is responsible only for high-level orchestration:
- validate input
- create job workspace
- copy original file
- build initial metadata
- persist initial artifacts
- prepare PDF pages for layout
- call the external layout service
- return job_id

IMPORTANT:
This is still NOT doing OCR yet. Layout is delegated through the same HTTP
contract that will later be backed by PP-DocLayoutV3.
"""

from datetime import UTC, datetime

from orchestrator.app.config import OUTPUT_DIR
from orchestrator.app.job_metadata import (
    append_log_line,
    build_initial_meta,
    build_initial_trace,
    write_json,
)
from orchestrator.app.job_workspace import (
    copy_original_file,
    create_job_dirs,
    generate_job_id,
    validate_input_file,
)
from orchestrator.app.layout_assets_stage import run_layout_assets_stage
from orchestrator.app.layout_stage import run_layout_stage
from orchestrator.app.preparing_for_layout import run_preparing_for_layout_stage


def start_job(input_path: str, dpi: int = 300) -> str:
    """
    Entry point for pipeline execution.

    Steps:
    1. Validate input file exists
    2. Generate job_id
    3. Create job folder structure
    4. Copy original file
    5. Build meta.json / trace.json / logs.jsonl
    6. Render PDF pages for layout
    7. Run layout service stage
    8. Return job_id
    """
    # ---- 1. Validate input ----
    src = validate_input_file(input_path)

    # ---- 2. Generate job id ----
    job_id = generate_job_id()

    # ---- 3. Create job folder structure ----
    job_dir = OUTPUT_DIR / job_id
    paths = create_job_dirs(job_dir)

    # ---- 4. Copy original file ----
    copied_file = copy_original_file(src, paths["original_dir"])

    # ---- 5. Build metadata artifacts ----
    now = datetime.now(UTC).isoformat()

    meta = build_initial_meta(
        job_id=job_id,
        src=src,
        copied_file=copied_file,
        paths=paths,
        now=now,
    )

    trace = build_initial_trace(
        job_id=job_id,
        input_path=src,
        now=now,
    )

    log_line = {
        "ts": now,
        "level": "INFO",
        "stage": "job",
        "message": "Job created",
        "job_id": job_id,
    }

    # ---- 6. Persist artifacts ----
    write_json(job_dir / "meta.json", meta)
    write_json(job_dir / "trace.json", trace)
    append_log_line(job_dir / "logs.jsonl", log_line)

    # ---- 6. Prepare PDF pages for layout ----
    rendered_pages = run_preparing_for_layout_stage(
        job_id=job_id,
        copied_file=copied_file,
        paths=paths,
        meta=meta,
        trace=trace,
        dpi=dpi,
    )
    write_json(job_dir / "meta.json", meta)
    write_json(job_dir / "trace.json", trace)

    # ---- 7. Run layout service stage ----
    normalized_layout_artifacts = run_layout_stage(
        job_id=job_id,
        copied_file=copied_file,
        paths=paths,
        meta=meta,
        trace=trace,
        rendered_pages=rendered_pages,
    )
    write_json(job_dir / "meta.json", meta)
    write_json(job_dir / "trace.json", trace)

    # ---- 8. Create layout-derived crops and visual overlays ----
    run_layout_assets_stage(
        job_id=job_id,
        paths=paths,
        meta=meta,
        trace=trace,
        normalized_artifact_paths=normalized_layout_artifacts,
    )
    write_json(job_dir / "meta.json", meta)
    write_json(job_dir / "trace.json", trace)

    # ---- Future pipeline stages placeholders ----
    # TODO: OCR stage
    # TODO: assembly stage

    return job_id
