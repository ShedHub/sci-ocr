"""
Prepare source PDF pages for the layout stage.

The layout service should receive rendered page images, not raw PDF files.
This module owns PDF-to-PNG rendering and writes deterministic page assets into
the job workspace before layout is executed.
"""

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from orchestrator.app.job_metadata import append_log_line, write_json


SUPPORTED_DPI = {300, 400}


def validate_render_dpi(dpi: int) -> int:
    """
    Keep the public API intentionally small: standard quality or high quality.
    """
    if dpi not in SUPPORTED_DPI:
        raise ValueError("dpi must be either 300 or 400")

    return dpi


def _load_fitz():
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is required for PDF page rendering. "
            "Install dependencies from requirements.txt."
        ) from exc

    return fitz


def render_pdf_pages(pdf_path: Path, pages_dir: Path, dpi: int) -> list[dict]:
    """
    Render every PDF page as PNG and return per-page metadata.
    """
    fitz = _load_fitz()
    dpi = validate_render_dpi(dpi)

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF input is supported for page rendering")

    rendered_pages: list[dict] = []
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    with fitz.open(pdf_path) as document:
        if document.page_count == 0:
            raise ValueError("PDF has no pages")

        for page_index in range(document.page_count):
            page_number = page_index + 1
            image_path = pages_dir / f"page_{page_number:04d}.png"
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            pixmap.save(image_path)

            rendered_pages.append(
                {
                    "page_number": page_number,
                    "image_path": str(image_path.resolve()),
                    "width": pixmap.width,
                    "height": pixmap.height,
                    "dpi": dpi,
                    "format": "png",
                }
            )

    return rendered_pages


def run_preparing_for_layout_stage(
    job_id: str,
    copied_file: Path,
    paths: dict[str, Path],
    meta: dict,
    trace: dict,
    dpi: int = 300,
) -> list[dict]:
    """
    Render PDF pages and persist the page-rendering artifact manifest.
    """
    started = perf_counter()
    dpi = validate_render_dpi(dpi)
    rendered_pages = render_pdf_pages(copied_file, paths["pages_dir"], dpi)

    now = datetime.now(UTC).isoformat()
    manifest = {
        "stage": "preparing_for_layout",
        "status": "completed",
        "job_id": job_id,
        "source_pdf": str(copied_file.resolve()),
        "dpi": dpi,
        "format": "png",
        "pages": rendered_pages,
        "service_time_ms": int((perf_counter() - started) * 1000),
    }
    manifest_path = paths["debug_dir"] / "preparing_for_layout.json"
    write_json(manifest_path, manifest)

    meta["status"] = "pages_prepared"
    meta["updated_at"] = now
    meta["stages"].append(
        {
            "name": "preparing_for_layout",
            "status": "completed",
            "pages": len(rendered_pages),
            "dpi": dpi,
            "format": "png",
            "artifacts": {
                "manifest": str(manifest_path.resolve()),
                "pages_dir": str(paths["pages_dir"].resolve()),
            },
        }
    )

    trace["events"].append(
        {
            "ts": now,
            "stage": "preparing_for_layout",
            "event": "pages_rendered",
            "details": {
                "pages": len(rendered_pages),
                "dpi": dpi,
                "format": "png",
            },
        }
    )

    append_log_line(
        paths["job_dir"] / "logs.jsonl",
        {
            "ts": now,
            "level": "INFO",
            "stage": "preparing_for_layout",
            "message": "PDF pages rendered for layout",
            "job_id": job_id,
            "pages": len(rendered_pages),
            "dpi": dpi,
        },
    )

    return rendered_pages
