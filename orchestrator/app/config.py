# config.py

from pathlib import Path

# Root of the whole project (cross-platform safe)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Jobs folder (artifact storage)
JOBS_DIR = PROJECT_ROOT / "jobs"

# Where input files may be stored (optional usage later)
INPUT_DIR = JOBS_DIR / "input"

# Where ALL pipeline results will be written
OUTPUT_DIR = JOBS_DIR / "output"
