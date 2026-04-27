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

# HTTP layout backend. Docker Compose overrides this for container-to-container calls.
LAYOUT_SERVICE_URL = os.getenv("LAYOUT_SERVICE_URL", "http://127.0.0.1:8001")

# Real CPU layout backends can take longer than stubs.
LAYOUT_TIMEOUT_SECONDS = float(os.getenv("LAYOUT_TIMEOUT_SECONDS", "10"))

# HTTP OCR backend. Docker Compose points this at ocr_glm; local dev may use ocr_stub.
OCR_SERVICE_URL = os.getenv("OCR_SERVICE_URL", "http://127.0.0.1:8002")

# OCR can be slow on CPU-backed real models; stubs keep using the fast default.
OCR_TIMEOUT_SECONDS = float(os.getenv("OCR_TIMEOUT_SECONDS", "30"))
