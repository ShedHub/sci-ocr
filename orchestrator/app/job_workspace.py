"""
Workspace helpers for pipeline jobs.

This module is responsible for:
- input validation
- job id generation
- job folder creation
- copying the original input file
"""

import shutil
import uuid
from datetime import datetime
from pathlib import Path


def generate_job_id() -> str:
    """
    Generate unique job id:
    job-YYYYMMDD-HHMMSS-xxxxxx

    Why:
    - human-readable timestamp
    - uniqueness (uuid suffix)
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    short_id = uuid.uuid4().hex[:6]
    return f"job-{timestamp}-{short_id}"


def validate_input_file(input_path: str) -> Path:
    """
    Validate that input_path exists and points to a file.

    Returns:
        Resolved Path to the source file.

    Raises:
        FileNotFoundError: if path does not exist
        ValueError: if path exists but is not a file
    """
    src = Path(input_path)

    if not src.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")

    if not src.is_file():
        raise ValueError(f"Input path is not a file: {input_path}")

    return src


def create_job_dirs(job_dir: Path) -> dict[str, Path]:
    """
    Create the standard folder structure for one job.

    Structure:
        jobs/output/<job_id>/
        ├─ original/
        ├─ preprocessed/
        ├─ assets/
        │  ├─ pages/
        │  └─ layout/
        └─ debug/

    Returns:
        Dictionary of useful paths for later pipeline stages.
    """
    paths = {
        "job_dir": job_dir,
        "original_dir": job_dir / "original",
        "preprocessed_dir": job_dir / "preprocessed",
        "assets_dir": job_dir / "assets",
        "pages_dir": job_dir / "assets" / "pages",
        "crops_dir": job_dir / "assets" / "crops",
        "layout_dir": job_dir / "assets" / "layout",
        "debug_dir": job_dir / "debug",
        "output_dir": job_dir / "output",
    }

    # Create root folder first
    paths["job_dir"].mkdir(parents=True, exist_ok=False)

    # Create child folders
    for key, path in paths.items():
        if key == "job_dir":
            continue
        path.mkdir()

    return paths


def copy_original_file(src: Path, original_dir: Path) -> Path:
    """
    Copy the input file into the job's original/ folder.

    Returns:
        Path to the copied file inside the workspace.
    """
    copied_file = original_dir / src.name
    shutil.copy2(src, copied_file)
    return copied_file
