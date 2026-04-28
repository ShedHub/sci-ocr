import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.app.vision_stage import run_vision_stage  # noqa: E402


def test_vision_stage_processes_routed_crops(tmp_path, monkeypatch) -> None:
    paths = {
        "job_dir": tmp_path,
        "debug_dir": tmp_path / "debug",
    }
    paths["debug_dir"].mkdir()
    crop_path = tmp_path / "crop.png"
    crop_path.write_bytes(b"not a real image but stage only passes the path")
    meta = {"status": "ocr_completed", "stages": []}
    trace = {"events": []}
    layout_asset_pages = [
        {
            "page_number": 1,
            "crops": [
                {
                    "page_number": 1,
                    "block_id": "p1_b1",
                    "type": "figure",
                    "layout_label": "chart",
                    "bbox": [1, 2, 30, 40],
                    "order": 1,
                    "image_path": str(crop_path),
                    "routing": {
                        "target_service": "vision",
                        "recognition_task": "chart",
                        "requested_format": "none",
                        "content_role": "chart",
                    },
                }
            ],
        }
    ]

    monkeypatch.setattr(
        "orchestrator.app.vision_stage.check_vision_service_ready",
        lambda *_args, **_kwargs: {},
    )

    def fake_call_vision_service(request: dict, *_args, **_kwargs) -> dict:
        return {
            "status": "completed",
            "job_id": request["job_id"],
            "document_id": request["document_id"],
            "page_number": request["page_number"],
            "block_id": request["block_id"],
            "content_role": request["content_role"],
            "recognition_task": request["recognition_task"],
            "visual_type": "chart_or_plot",
            "format": "markdown",
            "content": "Visual type: chart_or_plot\n\nApproximate chart data.",
            "structured_data": {},
            "confidence": None,
            "model": {
                "name": "vision_llama",
                "version": "local",
            },
            "warnings": [],
            "error": None,
            "service_time_ms": 1,
        }

    monkeypatch.setattr(
        "orchestrator.app.vision_stage.call_vision_service",
        fake_call_vision_service,
    )

    run_vision_stage(
        job_id="job-test",
        document_id="doc.pdf",
        paths=paths,
        meta=meta,
        trace=trace,
        layout_asset_pages=layout_asset_pages,
        vision_service_url="http://vision",
    )

    normalized = json.loads(
        (paths["debug_dir"] / "vision_normalized_page_0001.json").read_text(
            encoding="utf-8"
        )
    )
    pending = json.loads(
        (paths["debug_dir"] / "vision_pending_manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert meta["stages"][0]["name"] == "vision"
    assert meta["stages"][0]["status"] == "completed"
    assert normalized["blocks"][0]["visual_type"] == "chart_or_plot"
    assert pending["status"] == "completed"
    assert pending["block_count"] == 0


def test_vision_stage_leaves_blocks_pending_when_unconfigured(tmp_path) -> None:
    paths = {
        "job_dir": tmp_path,
        "debug_dir": tmp_path / "debug",
    }
    paths["debug_dir"].mkdir()
    meta = {"status": "ocr_completed", "stages": []}
    trace = {"events": []}
    layout_asset_pages = [
        {
            "page_number": 1,
            "crops": [
                {
                    "page_number": 1,
                    "block_id": "p1_b1",
                    "type": "figure",
                    "layout_label": "image",
                    "bbox": [1, 2, 30, 40],
                    "order": 1,
                    "image_path": "crop.png",
                    "routing": {
                        "target_service": "vision",
                        "recognition_task": "image",
                        "requested_format": "none",
                        "content_role": "image",
                    },
                }
            ],
        }
    ]

    run_vision_stage(
        job_id="job-test",
        document_id="doc.pdf",
        paths=paths,
        meta=meta,
        trace=trace,
        layout_asset_pages=layout_asset_pages,
        vision_service_url=None,
    )

    pending = json.loads(
        (paths["debug_dir"] / "vision_pending_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert meta["stages"][0]["status"] == "pending"
    assert pending["block_count"] == 1
