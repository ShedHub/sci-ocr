import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.app import pipeline  # noqa: E402


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

    job_id = pipeline.start_job(str(input_file), dpi=400)
    job_dir = output_dir / job_id

    assert (job_dir / "meta.json").is_file()
    assert (job_dir / "trace.json").is_file()
    assert (job_dir / "logs.jsonl").is_file()
    assert (job_dir / "original" / "input.pdf").is_file()
    assert (job_dir / "assets" / "pages" / "page_0001.png").is_file()
    assert (job_dir / "debug" / "preparing_for_layout.json").is_file()
    assert (job_dir / "debug" / "layout_raw_page_0001.json").is_file()
    assert (job_dir / "debug" / "layout_normalized_page_0001.json").is_file()

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

    assert meta["status"] == "layout_completed"
    assert meta["stages"][0]["name"] == "preparing_for_layout"
    assert meta["stages"][0]["dpi"] == 400
    assert meta["stages"][1]["name"] == "layout"
    assert preparing["dpi"] == 400
    assert preparing["pages"][0]["format"] == "png"
    assert normalized["source"] == "layout_stub"
    assert normalized["blocks"][0]["type"] == "text"
