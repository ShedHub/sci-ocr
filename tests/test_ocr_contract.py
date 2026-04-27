import pytest
from pydantic import ValidationError

from shared.contracts.ocr import OcrRequest, OcrResponse


def valid_ocr_request() -> dict:
    return {
        "job_id": "job-1",
        "document_id": "doc.pdf",
        "page_number": 1,
        "block_id": "p1_b1",
        "block_type": "table",
        "layout_label": "table",
        "content_role": "table",
        "recognition_task": "table",
        "requested_format": "markdown",
        "image_path": "/tmp/p1_b1.png",
        "bbox": [10, 20, 100, 120],
        "order": 1,
    }


def valid_ocr_response() -> dict:
    return {
        "status": "completed",
        "job_id": "job-1",
        "document_id": "doc.pdf",
        "page_number": 1,
        "block_id": "p1_b1",
        "content_role": "table",
        "recognition_task": "table",
        "format": "markdown",
        "content": "| A | B |",
        "confidence": 0.99,
        "model": {
            "name": "ocr_stub",
            "version": "0.1.0",
        },
        "warnings": [],
        "error": None,
        "service_time_ms": 1,
    }


def test_ocr_request_accepts_contract_shape() -> None:
    request = OcrRequest.model_validate(valid_ocr_request())

    assert request.recognition_task == "table"
    assert request.requested_format == "markdown"


def test_ocr_request_rejects_formula_markdown_mismatch() -> None:
    payload = valid_ocr_request()
    payload["recognition_task"] = "formula"

    with pytest.raises(ValidationError):
        OcrRequest.model_validate(payload)


def test_ocr_response_accepts_contract_shape() -> None:
    response = OcrResponse.model_validate(valid_ocr_response())

    assert response.status == "completed"
    assert response.content == "| A | B |"


def test_failed_ocr_response_requires_error() -> None:
    payload = valid_ocr_response()
    payload["status"] = "failed"

    with pytest.raises(ValidationError):
        OcrResponse.model_validate(payload)
