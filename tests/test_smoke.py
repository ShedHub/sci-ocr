import json
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.app import pipeline  # noqa: E402
from orchestrator.app import layout_stage  # noqa: E402
from orchestrator.app import ocr_stage  # noqa: E402
from orchestrator.app.layout_stage import LayoutServiceError  # noqa: E402


def create_test_pdf(path: Path) -> None:
    import fitz

    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((72, 72), "SCI-OCR test page")
    document.save(path)
    document.close()


def test_start_job_creates_layout_artifacts(tmp_path, monkeypatch) -> None:
    input_file = tmp_path / "input.pdf"
    create_test_pdf(input_file)

    output_dir = tmp_path / "jobs" / "output"
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(layout_stage, "check_layout_service_ready", lambda *_: {})
    monkeypatch.setattr(ocr_stage, "check_ocr_service_ready", lambda *_: {})

    def fake_call_layout_service(request: dict, *_args, **_kwargs) -> dict:
        return {
            "status": "completed",
            "job_id": request["job_id"],
            "document_id": request["document_id"],
            "page_number": request["page_number"],
            "model": {
                "name": "layout_stub",
                "version": "0.1.0",
            },
            "image": {
                "path": request["image_path"],
                "width": 3306,
                "height": 4678,
            },
            "blocks": [
                {
                    "block_id": f"p{request['page_number']}_b1",
                    "type": "text",
                    "layout_label": "content",
                    "bbox": [100, 100, 700, 180],
                    "confidence": 0.98,
                    "order": 1,
                },
                {
                    "block_id": f"p{request['page_number']}_b2",
                    "type": "table",
                    "layout_label": "table",
                    "bbox": [100, 220, 900, 500],
                    "confidence": 0.95,
                    "order": 2,
                },
                {
                    "block_id": f"p{request['page_number']}_b3",
                    "type": "formula",
                    "layout_label": "display_formula",
                    "bbox": [100, 540, 700, 620],
                    "confidence": 0.93,
                    "order": 3,
                },
                {
                    "block_id": f"p{request['page_number']}_b4",
                    "type": "figure",
                    "layout_label": "chart",
                    "bbox": [100, 660, 900, 900],
                    "confidence": 0.91,
                    "order": 4,
                }
            ],
            "warnings": [],
            "error": None,
            "service_time_ms": 1,
        }

    monkeypatch.setattr(layout_stage, "call_layout_service", fake_call_layout_service)

    def fake_call_ocr_service(request: dict, *_args, **_kwargs) -> dict:
        return {
            "status": "completed",
            "job_id": request["job_id"],
            "document_id": request["document_id"],
            "page_number": request["page_number"],
            "block_id": request["block_id"],
            "content_role": request["content_role"],
            "recognition_task": request["recognition_task"],
            "format": request["requested_format"],
            "content": f"{request['recognition_task']}:{request['block_id']}",
            "confidence": 1.0,
            "model": {
                "name": "ocr_stub",
                "version": "0.1.0",
            },
            "warnings": [],
            "error": None,
            "service_time_ms": 1,
        }

    monkeypatch.setattr(ocr_stage, "call_ocr_service", fake_call_ocr_service)

    job_id = pipeline.start_job(str(input_file), dpi=400)
    job_dir = output_dir / job_id

    assert (job_dir / "meta.json").is_file()
    assert (job_dir / "trace.json").is_file()
    assert (job_dir / "logs.jsonl").is_file()
    assert (job_dir / "original" / "input.pdf").is_file()
    assert (job_dir / "assets" / "pages" / "page_0001.png").is_file()
    assert (job_dir / "assets" / "crops" / "page_0001" / "p1_b1.png").is_file()
    assert (job_dir / "assets" / "crops" / "page_0001" / "p1_b2.png").is_file()
    assert (job_dir / "assets" / "crops" / "page_0001" / "p1_b3.png").is_file()
    assert (job_dir / "assets" / "crops" / "page_0001" / "p1_b4.png").is_file()
    assert (job_dir / "assets" / "layout" / "page_0001_layout.png").is_file()
    assert (job_dir / "debug" / "preparing_for_layout.json").is_file()
    assert (job_dir / "debug" / "layout_raw_page_0001.json").is_file()
    assert (job_dir / "debug" / "layout_normalized_page_0001.json").is_file()
    assert (job_dir / "debug" / "layout_assets.json").is_file()
    assert (job_dir / "debug" / "ocr_manifest.json").is_file()
    assert (job_dir / "debug" / "ocr_raw_page_0001.json").is_file()
    assert (job_dir / "debug" / "ocr_normalized_page_0001.json").is_file()
    assert (job_dir / "debug" / "vision_pending_manifest.json").is_file()

    meta = json.loads((job_dir / "meta.json").read_text(encoding="utf-8"))
    preparing = json.loads(
        (job_dir / "debug" / "preparing_for_layout.json").read_text(
            encoding="utf-8"
        )
    )
    normalized = json.loads(
        (job_dir / "debug" / "layout_normalized_page_0001.json").read_text(
            encoding="utf-8"
        )
    )
    layout_assets = json.loads(
        (job_dir / "debug" / "layout_assets.json").read_text(encoding="utf-8")
    )
    ocr_normalized = json.loads(
        (job_dir / "debug" / "ocr_normalized_page_0001.json").read_text(
            encoding="utf-8"
        )
    )
    vision_pending = json.loads(
        (job_dir / "debug" / "vision_pending_manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert meta["status"] == "ocr_completed"
    assert meta["stages"][0]["name"] == "preparing_for_layout"
    assert meta["stages"][0]["dpi"] == 400
    assert meta["stages"][1]["name"] == "layout"
    assert meta["stages"][2]["name"] == "layout_assets"
    assert meta["stages"][2]["crops"] == 4
    assert meta["stages"][3]["name"] == "vision"
    assert meta["stages"][3]["status"] == "pending"
    assert meta["stages"][4]["name"] == "ocr"
    assert meta["stages"][4]["blocks"] == 3
    assert meta["stages"][4]["vision_pending_blocks"] == 1
    assert preparing["dpi"] == 400
    assert preparing["pages"][0]["format"] == "png"
    assert normalized["source"] == "layout_stub"
    assert normalized["blocks"][0]["type"] == "text"
    assert normalized["blocks"][0]["layout_label"] == "content"
    assert len(layout_assets["pages"][0]["crops"]) == 4
    assert layout_assets["pages"][0]["crops"][1]["routing"]["recognition_task"] == "table"
    assert layout_assets["pages"][0]["crops"][2]["routing"]["requested_format"] == "latex"
    assert layout_assets["pages"][0]["crops"][3]["routing"]["target_service"] == "vision"
    assert layout_assets["pages"][0]["crops"][3]["routing"]["recognition_task"] == "chart"
    assert len(ocr_normalized["blocks"]) == 3
    assert ocr_normalized["blocks"][0]["format"] == "markdown"
    assert ocr_normalized["blocks"][1]["recognition_task"] == "table"
    assert ocr_normalized["blocks"][2]["format"] == "latex"
    assert vision_pending["status"] == "pending"
    assert vision_pending["block_count"] == 1


def test_layout_failure_is_persisted(tmp_path, monkeypatch) -> None:
    input_file = tmp_path / "input.pdf"
    create_test_pdf(input_file)

    output_dir = tmp_path / "jobs" / "output"
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", output_dir)

    def fail_ready(*_args, **_kwargs) -> dict:
        raise LayoutServiceError("layout service unavailable")

    monkeypatch.setattr(layout_stage, "check_layout_service_ready", fail_ready)

    with pytest.raises(LayoutServiceError):
        pipeline.start_job(str(input_file), dpi=300)

    job_dirs = list(output_dir.iterdir())
    assert len(job_dirs) == 1

    job_dir = job_dirs[0]
    meta = json.loads((job_dir / "meta.json").read_text(encoding="utf-8"))
    trace = json.loads((job_dir / "trace.json").read_text(encoding="utf-8"))
    logs = (job_dir / "logs.jsonl").read_text(encoding="utf-8").splitlines()
    last_log = json.loads(logs[-1])

    assert meta["status"] == "layout_failed"
    assert meta["stages"][-1]["name"] == "layout"
    assert meta["stages"][-1]["status"] == "failed"
    assert trace["events"][-1]["stage"] == "layout"
    assert trace["events"][-1]["event"] == "failed"
    assert last_log["level"] == "ERROR"
    assert last_log["stage"] == "layout"
