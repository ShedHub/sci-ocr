from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
JOBS_DIR = PROJECT_ROOT / "jobs"
INPUT_DIR = JOBS_DIR / "input"
OUTPUT_DIR = JOBS_DIR / "output"
