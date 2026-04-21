# pipeline.py

"""
Pipeline entry point.

This file is responsible for:
- validating input
- creating a job workspace
- saving metadata
- returning job_id

IMPORTANT:
This is NOT doing OCR yet.
This step only creates a persistent job on disk.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
import uuid

from orchestrator.app.config import OUTPUT_DIR


def generate_job_id() -> str:
    """
    Generate unique job id:
    job-YYYYMMDD-HHMMSS-xxxx

    Why:
    - human-readable timestamp
    - uniqueness (uuid suffix)
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    short_id = uuid.uuid4().hex[:6]
    return f"job-{timestamp}-{short_id}"


def start_job(input_path: str) -> str:
    """
    Entry point for pipeline execution.

    Steps:
    1. Validate input file exists
    2. Generate job_id
    3. Create job folder
    4. Copy original file
    5. Write meta.json / trace.json / logs.jsonl
    6. Return job_id
    """

    # ---- 1. Validate input ----
    src = Path(input_path)

    if not src.exists():
        # Fail early → API will convert to HTTP 404
        raise FileNotFoundError(f"Input file does not exist: {input_path}")

    if not src.is_file():
        raise ValueError(f"Input path is not a file: {input_path}")

    # ---- 2. Generate job id ----
    job_id = generate_job_id()

    # ---- 3. Create job folder ----
    job_dir = OUTPUT_DIR / job_id
    original_dir = job_dir / "original"

    # Each job gets isolated workspace
    original_dir.mkdir(parents=True, exist_ok=False)

    # ---- 4. Copy original file ----
    copied_file = original_dir / src.name
    shutil.copy2(src, copied_file)

    # ---- 5. Create metadata ----

    # meta.json → main summary of job
    meta = {
        "job_id": job_id,
        "status": "created",
        "input": {
            "original_path": str(src.resolve()),
            "copied_path": str(copied_file.resolve()),
            "filename": src.name,
        },
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "stages": [],  # later: layout, ocr, assembly
    }

    # trace.json → timeline of events
    trace = {
        "job_id": job_id,
        "events": [
            {
                "ts": datetime.utcnow().isoformat(),
                "stage": "job",
                "event": "created",
                "details": {
                    "input_path": str(src.resolve()),
                },
            }
        ],
    }

    # logs.jsonl → appendable logs (one JSON per line)
    log_line = {
        "ts": datetime.utcnow().isoformat(),
        "level": "INFO",
        "stage": "job",
        "message": "Job created",
        "job_id": job_id,
    }

    # ---- Write files ----

    # meta.json
    (job_dir / "meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )

    # trace.json
    (job_dir / "trace.json").write_text(
        json.dumps(trace, indent=2), encoding="utf-8"
    )

    # logs.jsonl (append-friendly format)
    with open(job_dir / "logs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_line) + "\n")

    # ---- Future pipeline stages placeholders ----
    # TODO: layout stage
    # TODO: OCR stage
    # TODO: assembly stage

    return job_id
