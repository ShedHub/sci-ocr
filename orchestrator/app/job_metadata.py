"""
Metadata and logging helpers for pipeline jobs.

This module is responsible for:
- building initial meta.json
- building initial trace.json
- writing JSON files
- appending JSONL log lines
"""

import json
from pathlib import Path


def build_workspace_snapshot(paths: dict[str, Path]) -> dict[str, str]:
    """
    Convert workspace paths into a JSON-serializable dictionary.
    """
    return {
        "job_dir": str(paths["job_dir"].resolve()),
        "original_dir": str(paths["original_dir"].resolve()),
        "preprocessed_dir": str(paths["preprocessed_dir"].resolve()),
        "assets_dir": str(paths["assets_dir"].resolve()),
        "pages_dir": str(paths["pages_dir"].resolve()),
        "crops_dir": str(paths["crops_dir"].resolve()),
        "layout_dir": str(paths["layout_dir"].resolve()),
        "debug_dir": str(paths["debug_dir"].resolve()),
    }


def build_initial_meta(
    job_id: str,
    src: Path,
    copied_file: Path,
    paths: dict[str, Path],
    now: str,
) -> dict:
    """
    Build the initial contents of meta.json.
    """
    return {
        "job_id": job_id,
        "status": "created",
        "input": {
            "original_path": str(src.resolve()),
            "copied_path": str(copied_file.resolve()),
            "filename": src.name,
        },
        "workspace": build_workspace_snapshot(paths),
        "created_at": now,
        "updated_at": now,
        "stages": [],
    }


def build_initial_trace(job_id: str, input_path: Path, now: str) -> dict:
    """
    Build the initial contents of trace.json.
    """
    return {
        "job_id": job_id,
        "events": [
            {
                "ts": now,
                "stage": "job",
                "event": "created",
                "details": {
                    "input_path": str(input_path.resolve()),
                },
            }
        ],
    }


def write_json(path: Path, payload: dict) -> None:
    """
    Write JSON file with UTF-8 encoding and pretty formatting.
    """
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def append_log_line(path: Path, payload: dict) -> None:
    """
    Append one JSON object as a line to a .jsonl file.
    """
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
