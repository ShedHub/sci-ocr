# pipeline.py
"""
Pipeline entry point.

This module is responsible only for high-level orchestration:
- validate input
- create job workspace
- copy original file
- build initial metadata
- persist initial artifacts
- return job_id

IMPORTANT:
This is still NOT doing OCR yet.
This step only creates a persistent job on disk.
"""

from datetime import datetime

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


def start_job(input_path: str) -> str:
    """
    Entry point for pipeline execution.

    Steps:
    1. Validate input file exists
    2. Generate job_id
    3. Create job folder structure
    4. Copy original file
    5. Build meta.json / trace.json / logs.jsonl
    6. Return job_id
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
    now = datetime.utcnow().isoformat()

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

    # ---- Future pipeline stages placeholders ----
    # TODO: layout stage
    # TODO: OCR stage
    # TODO: assembly stage

    return job_id