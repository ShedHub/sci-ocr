import json
from pathlib import Path

from orchestrator.app.assembly_stage import build_content_stream, render_markdown


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_assembly_builds_ordered_stream_and_markdown(tmp_path) -> None:
    paths = {
        "debug_dir": tmp_path / "debug",
    }

    write_json(
        paths["debug_dir"] / "layout_normalized_page_0001.json",
        {
            "stage": "layout",
            "status": "completed",
            "source": "fixture_layout",
            "job_id": "job-test",
            "page_number": 1,
            "image": {"path": "page.png", "width": 100, "height": 100},
            "blocks": [
                {
                    "block_id": "p1_b2",
                    "type": "formula",
                    "layout_label": "display_formula",
                    "bbox": [10, 40, 80, 50],
                    "confidence": 0.9,
                    "order": 2,
                    "source": "fixture_layout",
                },
                {
                    "block_id": "p1_b1",
                    "type": "title",
                    "layout_label": "doc_title",
                    "bbox": [10, 10, 80, 30],
                    "confidence": 0.9,
                    "order": 1,
                    "source": "fixture_layout",
                },
                {
                    "block_id": "p1_b3",
                    "type": "figure",
                    "layout_label": "chart",
                    "bbox": [10, 60, 80, 90],
                    "confidence": 0.9,
                    "order": 3,
                    "source": "fixture_layout",
                },
            ],
            "warnings": [],
        },
    )
    write_json(
        paths["debug_dir"] / "layout_assets.json",
        {
            "stage": "layout_assets",
            "status": "completed",
            "job_id": "job-test",
            "pages": [
                {
                    "page_number": 1,
                    "crops": [
                        {
                            "page_number": 1,
                            "block_id": "p1_b1",
                            "image_path": "p1_b1.png",
                            "routing": {
                                "target_service": "ocr",
                                "recognition_task": "text",
                                "requested_format": "markdown",
                                "content_role": "title",
                            },
                        },
                        {
                            "page_number": 1,
                            "block_id": "p1_b2",
                            "image_path": "p1_b2.png",
                            "routing": {
                                "target_service": "ocr",
                                "recognition_task": "formula",
                                "requested_format": "latex",
                                "content_role": "formula",
                            },
                        },
                        {
                            "page_number": 1,
                            "block_id": "p1_b3",
                            "image_path": "p1_b3.png",
                            "routing": {
                                "target_service": "vision",
                                "recognition_task": "chart",
                                "requested_format": "none",
                                "content_role": "chart",
                            },
                        },
                    ],
                }
            ],
        },
    )
    write_json(
        paths["debug_dir"] / "ocr_normalized_page_0001.json",
        {
            "stage": "ocr",
            "status": "completed",
            "source": "ocr_stub",
            "job_id": "job-test",
            "page_number": 1,
            "blocks": [
                {
                    "job_id": "job-test",
                    "page_number": 1,
                    "block_id": "p1_b1",
                    "content_role": "title",
                    "recognition_task": "text",
                    "format": "markdown",
                    "content": "A Science Article",
                    "bbox": [10, 10, 80, 30],
                    "order": 1,
                    "image_path": "p1_b1.png",
                    "source": "ocr_stub",
                    "warnings": [],
                },
                {
                    "job_id": "job-test",
                    "page_number": 1,
                    "block_id": "p1_b2",
                    "content_role": "formula",
                    "recognition_task": "formula",
                    "format": "latex",
                    "content": "E = mc^2",
                    "bbox": [10, 40, 80, 50],
                    "order": 2,
                    "image_path": "p1_b2.png",
                    "source": "ocr_stub",
                    "warnings": [],
                },
            ],
            "warnings": [],
        },
    )
    write_json(
        paths["debug_dir"] / "vision_pending_manifest.json",
        {
            "stage": "vision",
            "status": "pending",
            "job_id": "job-test",
            "blocks": [
                {
                    "page_number": 1,
                    "block_id": "p1_b3",
                    "routing": {"content_role": "chart", "recognition_task": "chart"},
                }
            ],
            "block_count": 1,
        },
    )

    stream, warnings = build_content_stream(paths)
    markdown = render_markdown(stream)

    assert warnings == []
    assert [entry["block_id"] for entry in stream] == ["p1_b1", "p1_b2", "p1_b3"]
    assert stream[2]["source"] == "vision_pending"
    assert markdown == "# A Science Article\n\n$$\nE = mc^2\n$$\n\n> [Chart pending: p1_b3]\n"
