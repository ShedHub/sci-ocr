from time import perf_counter

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


def run_layout(request: LayoutRequest) -> dict:
    started = perf_counter()

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
            "width": 1000,
            "height": 1400,
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
            "layout_stub did not read image_path because page rendering is not implemented yet"
        ],
        "error": None,
    }

    response["service_time_ms"] = int((perf_counter() - started) * 1000)
    return response
