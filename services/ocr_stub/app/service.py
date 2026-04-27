from pathlib import Path
from time import perf_counter

from shared.contracts.ocr import OcrReadyResponse, OcrRequest, OcrResponse


SERVICE_NAME = "ocr_stub"
MODEL_NAME = "ocr_stub"
MODEL_VERSION = "0.1.0"


def get_status() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


def get_ready() -> OcrReadyResponse:
    return OcrReadyResponse(
        status="ready",
        service=SERVICE_NAME,
        model=MODEL_NAME,
        version=MODEL_VERSION,
    )


def validate_crop_path(image_path: str) -> None:
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"image_path does not exist or is not a file: {image_path}")


def build_stub_content(request: OcrRequest) -> str:
    if request.recognition_task == "table":
        return (
            "| source | block_id | role |\n"
            "| --- | --- | --- |\n"
            f"| ocr_stub | {request.block_id} | {request.content_role} |"
        )

    if request.recognition_task == "formula":
        escaped_block_id = request.block_id.replace("_", "\\_")
        return f"\\mathrm{{ocr\\_stub}}_{{{escaped_block_id}}}"

    if request.content_role == "title":
        return f"# OCR stub text for {request.block_id}"

    if request.content_role == "heading":
        return f"## OCR stub text for {request.block_id}"

    return f"OCR stub text for {request.block_id}"


def run_ocr(request: OcrRequest) -> OcrResponse:
    started = perf_counter()
    validate_crop_path(request.image_path)

    return OcrResponse(
        status="completed",
        job_id=request.job_id,
        document_id=request.document_id,
        page_number=request.page_number,
        block_id=request.block_id,
        content_role=request.content_role,
        recognition_task=request.recognition_task,
        format=request.requested_format,
        content=build_stub_content(request),
        confidence=1.0,
        model={
            "name": MODEL_NAME,
            "version": MODEL_VERSION,
            "backend": SERVICE_NAME,
            "metadata": {},
        },
        warnings=[
            "ocr_stub validated the crop path but did not run real OCR"
        ],
        error=None,
        service_time_ms=int((perf_counter() - started) * 1000),
    )
