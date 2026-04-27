import sys
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.ocr_stub.app.main import app  # noqa: E402
from services.ocr_stub.app.service import run_ocr  # noqa: E402
from shared.contracts.ocr import OcrRequest  # noqa: E402


def build_request(tmp_path: Path, recognition_task: str, requested_format: str) -> OcrRequest:
    crop_path = tmp_path / "crop.png"
    crop_path.write_bytes(b"stub image bytes")

    return OcrRequest(
        job_id="job-1",
        document_id="doc.pdf",
        page_number=1,
        block_id="p1_b1",
        block_type=recognition_task,
        layout_label=recognition_task,
        content_role=recognition_task,
        recognition_task=recognition_task,
        requested_format=requested_format,
        image_path=str(crop_path),
        bbox=(1, 2, 30, 40),
        order=1,
    )


def test_ocr_stub_returns_markdown_for_tables(tmp_path) -> None:
    response = run_ocr(build_request(tmp_path, "table", "markdown"))

    assert response.format == "markdown"
    assert "| source | block_id | role |" in response.content


def test_ocr_stub_returns_latex_for_formulas(tmp_path) -> None:
    response = run_ocr(build_request(tmp_path, "formula", "latex"))

    assert response.format == "latex"
    assert "\\mathrm" in response.content


def test_ocr_stub_exposes_health_ready_and_ocr_endpoints(tmp_path) -> None:
    client = TestClient(app)
    request = build_request(tmp_path, "text", "markdown")

    health = client.get("/health")
    ready = client.get("/ready")
    ocr = client.post("/ocr", json=request.model_dump())

    assert health.status_code == 200
    assert health.json()["service"] == "ocr_stub"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ocr.status_code == 200
    assert ocr.json()["recognition_task"] == "text"
