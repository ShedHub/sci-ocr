import sys
from time import sleep
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.ocr_glm.app import service  # noqa: E402
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


def test_glm_prompt_selection_matches_recognition_tasks() -> None:
    assert service.prompt_for_task("text") == "Text Recognition:"
    assert service.prompt_for_task("table") == "Table Recognition:"
    assert service.prompt_for_task("formula") == "Formula Recognition:"


def test_glm_ocr_response_uses_shared_contract(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(service, "generate_content", lambda image_path, request: "recognized")
    response = service.run_ocr(build_request(tmp_path, "text", "markdown"))

    assert response.model.name == "GLM-OCR"
    assert response.model.backend == "ocr_glm"
    assert response.content == "recognized"
    assert response.format == "markdown"


def test_glm_formula_output_strips_display_wrappers(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        service,
        "generate_content",
        lambda image_path, request: "$$\nF_1 = \\frac{2PR}{P + R}\n$$",
    )
    response = service.run_ocr(build_request(tmp_path, "formula", "latex"))

    assert response.content == "F_1 = \\frac{2PR}{P + R}"


def test_glm_async_job_wraps_existing_ocr_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(service, "generate_content", lambda image_path, request: "recognized")
    started = service.start_ocr_job(build_request(tmp_path, "text", "markdown"))

    status = None
    for _ in range(50):
        status = service.get_ocr_job_status(started.task_id)
        if status.status == "completed":
            break
        sleep(0.01)

    assert status is not None
    assert status.status == "completed"
    assert status.stage == "completed"
    assert status.result is not None
    assert status.result.content == "recognized"
