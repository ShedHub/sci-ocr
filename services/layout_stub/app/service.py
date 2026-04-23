from time import perf_counter
from pathlib import Path
import struct

from pydantic import BaseModel, Field


LAYOUT_STUB_VERSION = "0.1.0"


class LayoutRequest(BaseModel):
    job_id: str
    document_id: str | None = None
    page_number: int = Field(ge=1)
    image_path: str


def get_status() -> dict[str, str]:
    return {"status": "ok", "service": "layout_stub"}


def get_ready() -> dict[str, str]:
    return {
        "status": "ready",
        "service": "layout_stub",
        "model": "layout_stub",
        "version": LAYOUT_STUB_VERSION,
    }


def read_png_dimensions(image_path: str) -> tuple[int, int]:
    """
    Read PNG dimensions from the file header to verify shared path access.
    """
    path = Path(image_path)
    if not path.is_file():
        raise ValueError(f"image_path does not exist or is not a file: {image_path}")

    with path.open("rb") as file:
        header = file.read(24)

    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"image_path is not a valid PNG file: {image_path}")

    width, height = struct.unpack(">II", header[16:24])
    return width, height


def run_layout(request: LayoutRequest) -> dict:
    started = perf_counter()
    image_width, image_height = read_png_dimensions(request.image_path)

    response = {
        "status": "completed",
        "job_id": request.job_id,
        "document_id": request.document_id,
        "page_number": request.page_number,
        "model": {
            "name": "layout_stub",
            "version": LAYOUT_STUB_VERSION,
        },
        "image": {
            "path": request.image_path,
            "width": image_width,
            "height": image_height,
        },
        "blocks": [
            {
                "block_id": f"p{request.page_number}_b1",
                "type": "text",
                "bbox": [100, 100, 700, 180],
                "confidence": 0.98,
                "order": 1,
            }
        ],
        "warnings": [
            "layout_stub read the rendered PNG dimensions but did not infer blocks from image content"
        ],
        "error": None,
    }

    response["service_time_ms"] = int((perf_counter() - started) * 1000)
    return response
