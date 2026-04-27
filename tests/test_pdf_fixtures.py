import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.app import layout_stage, ocr_stage, pipeline  # noqa: E402
from orchestrator.app.preparing_for_layout import render_pdf_pages  # noqa: E402
from scripts.generate_test_pdfs import generate_all  # noqa: E402


FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "pdfs"
MIXED_FIXTURE = FIXTURE_DIR / "science_mixed_content.pdf"
FORMULA_TABLE_FIXTURE = FIXTURE_DIR / "formula_table_fixture.pdf"


def test_generated_pdf_fixtures_exist_and_contain_expected_text(tmp_path) -> None:
    generated = generate_all(tmp_path)

    assert {path.name for path in generated} == {
        "science_mixed_content.pdf",
        "formula_table_fixture.pdf",
    }

    import fitz

    with fitz.open(generated[0]) as document:
        assert document.page_count == 2
        text = "\n".join(page.get_text() for page in document)
        mixed_image_count = sum(len(page.get_images(full=True)) for page in document)

    assert "SCI-OCR Mixed Content Fixture" in text
    assert "Formula block" in text
    assert "Figure 1" in text
    assert "Chart 1. Synthetic extraction benchmark" in text
    assert "Chart 2. Classic line graph" in text
    assert mixed_image_count >= 6

    with fitz.open(generated[1]) as document:
        assert document.page_count == 1
        text = document[0].get_text()
        image_count = len(document[0].get_images(full=True))

    assert "SCI-OCR Formula and Table Fixture" in text
    assert "Formula block" in text
    assert "Accuracy" in text
    assert image_count >= 3


def test_checked_in_pdf_fixtures_render_to_page_images(tmp_path) -> None:
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()

    rendered_pages = render_pdf_pages(MIXED_FIXTURE, pages_dir, dpi=300)

    assert len(rendered_pages) == 2
    assert rendered_pages[0]["format"] == "png"
    assert rendered_pages[0]["width"] > 0
    assert rendered_pages[0]["height"] > 0
    assert Path(rendered_pages[0]["image_path"]).is_file()
    assert Path(rendered_pages[1]["image_path"]).is_file()


def test_mixed_fixture_exercises_text_table_formula_and_vision_routes(
    tmp_path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "jobs" / "output"
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(layout_stage, "check_layout_service_ready", lambda *_: {})
    monkeypatch.setattr(ocr_stage, "check_ocr_service_ready", lambda *_: {})

    def fake_call_layout_service(request: dict, *_args, **_kwargs) -> dict:
        page_number = request["page_number"]
        if page_number == 1:
            blocks = [
                {
                    "block_id": "p1_b1",
                    "type": "title",
                    "layout_label": "doc_title",
                    "bbox": [50, 45, 950, 140],
                    "confidence": 0.99,
                    "order": 1,
                },
                {
                    "block_id": "p1_b2",
                    "type": "text",
                    "layout_label": "content",
                    "bbox": [50, 145, 950, 460],
                    "confidence": 0.96,
                    "order": 2,
                },
                {
                    "block_id": "p1_b3",
                    "type": "table",
                    "layout_label": "table",
                    "bbox": [50, 520, 950, 900],
                    "confidence": 0.95,
                    "order": 3,
                },
                {
                    "block_id": "p1_b4",
                    "type": "formula",
                    "layout_label": "display_formula",
                    "bbox": [50, 960, 950, 1260],
                    "confidence": 0.94,
                    "order": 4,
                },
            ]
        else:
            blocks = [
                {
                    "block_id": "p2_b1",
                    "type": "text",
                    "layout_label": "content",
                    "bbox": [50, 80, 950, 270],
                    "confidence": 0.96,
                    "order": 1,
                },
                {
                    "block_id": "p2_b2",
                    "type": "figure",
                    "layout_label": "image",
                    "bbox": [50, 340, 950, 860],
                    "confidence": 0.92,
                    "order": 2,
                },
                {
                    "block_id": "p2_b3",
                    "type": "text",
                    "layout_label": "figure_title",
                    "bbox": [50, 885, 950, 940],
                    "confidence": 0.93,
                    "order": 3,
                },
                {
                    "block_id": "p2_b4",
                    "type": "figure",
                    "layout_label": "chart",
                    "bbox": [50, 980, 500, 1260],
                    "confidence": 0.91,
                    "order": 4,
                },
                {
                    "block_id": "p2_b5",
                    "type": "figure",
                    "layout_label": "chart",
                    "bbox": [540, 980, 950, 1260],
                    "confidence": 0.91,
                    "order": 5,
                },
            ]

        return {
            "status": "completed",
            "job_id": request["job_id"],
            "document_id": request["document_id"],
            "page_number": page_number,
            "model": {
                "name": "fixture_layout",
                "version": "0.1.0",
            },
            "image": {
                "path": request["image_path"],
                "width": 2550,
                "height": 3300,
            },
            "blocks": blocks,
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
            "content": f"{request['content_role']}:{request['block_id']}",
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

    job_id = pipeline.start_job(str(MIXED_FIXTURE), dpi=300)
    job_dir = output_dir / job_id
    layout_assets = json.loads((job_dir / "debug" / "layout_assets.json").read_text(encoding="utf-8"))
    ocr_manifest = json.loads((job_dir / "debug" / "ocr_manifest.json").read_text(encoding="utf-8"))
    vision_pending = json.loads(
        (job_dir / "debug" / "vision_pending_manifest.json").read_text(encoding="utf-8")
    )
    page_1_ocr = json.loads(
        (job_dir / "debug" / "ocr_normalized_page_0001.json").read_text(encoding="utf-8")
    )

    crops = [crop for page in layout_assets["pages"] for crop in page["crops"]]
    routes = {crop["block_id"]: crop["routing"] for crop in crops}

    assert len(crops) == 9
    assert routes["p1_b1"]["content_role"] == "title"
    assert routes["p1_b3"]["recognition_task"] == "table"
    assert routes["p1_b4"]["requested_format"] == "latex"
    assert routes["p2_b2"]["target_service"] == "vision"
    assert routes["p2_b4"]["recognition_task"] == "chart"
    assert routes["p2_b5"]["recognition_task"] == "chart"
    assert ocr_manifest["blocks"] == 6
    assert ocr_manifest["vision_pending_blocks"] == 3
    assert vision_pending["block_count"] == 3
    assert {block["format"] for block in page_1_ocr["blocks"]} == {"markdown", "latex"}
