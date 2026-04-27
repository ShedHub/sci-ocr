import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_report_job_prints_stage_layout_routing_and_vision_summary(tmp_path) -> None:
    job_dir = tmp_path / "jobs" / "output" / "job-test"
    debug_dir = job_dir / "debug"
    debug_dir.mkdir(parents=True)

    write_json(
        job_dir / "meta.json",
        """
        {
          "job_id": "job-test",
          "status": "ocr_completed",
          "input": {"filename": "fixture.pdf"},
          "stages": [
            {"name": "layout", "status": "completed", "pages": 1, "blocks": 2, "source": "fixture_layout"},
            {"name": "vision", "status": "pending", "blocks": 1},
            {"name": "ocr", "status": "completed", "blocks": 1, "vision_pending_blocks": 1, "source": "ocr_stub"},
            {"name": "assembly", "status": "completed", "blocks": 2}
          ]
        }
        """,
    )
    write_json(
        debug_dir / "layout_normalized_page_0001.json",
        """
        {
          "stage": "layout",
          "status": "completed",
          "source": "fixture_layout",
          "job_id": "job-test",
          "page_number": 1,
          "image": {"path": "page.png", "width": 100, "height": 100},
          "blocks": [
            {"block_id": "p1_b1", "type": "text", "layout_label": "text", "bbox": [1, 1, 50, 20], "confidence": 0.9, "order": 1, "source": "fixture_layout"},
            {"block_id": "p1_b2", "type": "figure", "layout_label": "chart", "bbox": [1, 30, 80, 90], "confidence": 0.8, "order": 2, "source": "fixture_layout"}
          ],
          "warnings": []
        }
        """,
    )
    write_json(
        debug_dir / "layout_assets.json",
        """
        {
          "stage": "layout_assets",
          "status": "completed",
          "job_id": "job-test",
          "pages": [
            {
              "page_number": 1,
              "crops": [
                {"block_id": "p1_b1", "routing": {"target_service": "ocr", "recognition_task": "text", "requested_format": "markdown"}},
                {"block_id": "p1_b2", "routing": {"target_service": "vision", "recognition_task": "chart", "requested_format": "none"}}
              ]
            }
          ]
        }
        """,
    )
    write_json(
        debug_dir / "ocr_normalized_page_0001.json",
        """
        {
          "stage": "ocr",
          "status": "completed",
          "source": "ocr_stub",
          "job_id": "job-test",
          "page_number": 1,
          "blocks": [
            {"block_id": "p1_b1", "recognition_task": "text", "format": "markdown"}
          ],
          "warnings": []
        }
        """,
    )
    write_json(
        debug_dir / "vision_pending_manifest.json",
        """
        {
          "stage": "vision",
          "status": "pending",
          "job_id": "job-test",
          "blocks": [
            {"block_id": "p1_b2", "routing": {"content_role": "chart", "recognition_task": "chart"}}
          ],
          "block_count": 1
        }
        """,
    )
    write_json(
        debug_dir / "assembly_manifest.json",
        """
        {
          "stage": "assembly",
          "status": "completed",
          "job_id": "job-test",
          "blocks": 2,
          "sources": {"ocr_stub": 1, "vision_pending": 1},
          "statuses": {"completed": 1, "pending": 1},
          "artifacts": {
            "markdown": "article.md",
            "content_stream": "content_stream.json"
          }
        }
        """,
    )

    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "report_job.py"),
            "job-test",
            "--output-dir",
            str(tmp_path / "jobs" / "output"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Job: job-test" in result.stdout
    assert "layout: completed" in result.stdout
    assert "type summary: figure=1, text=1" in result.stdout
    assert "targets: ocr=1, vision=1" in result.stdout
    assert "pending blocks: 1" in result.stdout
    assert "Assembly:" in result.stdout
    assert "sources: ocr_stub=1, vision_pending=1" in result.stdout
