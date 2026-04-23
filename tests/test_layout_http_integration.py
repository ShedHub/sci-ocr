import json
import os
import sys
from pathlib import Path

import httpx
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.app import pipeline  # noqa: E402


LAYOUT_SERVICE_URL = os.getenv("LAYOUT_SERVICE_URL", "http://127.0.0.1:8001")


def create_test_pdf(path: Path) -> None:
    import fitz

    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((72, 72), "SCI-OCR integration page")
    document.save(path)
    document.close()


def require_layout_stub() -> None:
    try:
        response = httpx.get(
            f"{LAYOUT_SERVICE_URL.rstrip('/')}/ready",
            timeout=2.0,
            trust_env=False,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        pytest.skip(f"layout_stub is not available at {LAYOUT_SERVICE_URL}: {exc}")


def test_orchestrator_calls_real_layout_stub(tmp_path, monkeypatch) -> None:
    require_layout_stub()

    input_file = tmp_path / "input.pdf"
    create_test_pdf(input_file)

    output_dir = tmp_path / "jobs" / "output"
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", output_dir)

    job_id = pipeline.start_job(str(input_file), dpi=300)
    job_dir = output_dir / job_id

    meta = json.loads((job_dir / "meta.json").read_text(encoding="utf-8"))
    raw = json.loads(
        (job_dir / "debug" / "layout_raw_page_0001.json").read_text(
            encoding="utf-8"
        )
    )
    normalized = json.loads(
        (job_dir / "debug" / "layout_normalized_page_0001.json").read_text(
            encoding="utf-8"
        )
    )

    assert meta["status"] == "layout_completed"
    assert meta["stages"][1]["layout_service_url"] == LAYOUT_SERVICE_URL
    assert raw["model"]["name"] == "layout_stub"
    assert raw["image"]["width"] > 0
    assert raw["image"]["height"] > 0
    assert normalized["source"] == "layout_stub"
