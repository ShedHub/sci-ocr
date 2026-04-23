import os

from pathlib import Path

# Root of the whole project (cross-platform safe)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Jobs folder (artifact storage)
JOBS_DIR = PROJECT_ROOT / "jobs"

# Where input files may be stored (optional usage later)
INPUT_DIR = JOBS_DIR / "input"

# Where ALL pipeline results will be written
OUTPUT_DIR = JOBS_DIR / "output"

# HTTP layout backend. Docker Compose overrides this to http://layout_stub:8000.
LAYOUT_SERVICE_URL = os.getenv("LAYOUT_SERVICE_URL", "http://127.0.0.1:8001")
