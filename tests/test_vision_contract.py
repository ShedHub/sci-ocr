import pytest
from pydantic import ValidationError

from shared.contracts.vision import VisionRequest, VisionResponse


def valid_vision_request() -> dict:
    return {
        "job_id": "job-1",
        "document_id": "doc.pdf",
        "page_number": 1,
        "block_id": "p1_b1",
        "block_type": "figure",
        "layout_label": "chart",
        "content_role": "chart",
        "recognition_task": "chart",
        "requested_format": "none",
        "image_path": "/tmp/p1_b1.png",
        "bbox": [10, 20, 100, 120],
        "order": 1,
    }


def valid_vision_response() -> dict:
    return {
        "status": "completed",
        "job_id": "job-1",
        "document_id": "doc.pdf",
        "page_number": 1,
        "block_id": "p1_b1",
        "content_role": "chart",
        "recognition_task": "chart",
        "visual_type": "chart_or_plot",
        "format": "markdown",
        "content": "Visual type: chart_or_plot\n\nApproximate data.",
        "structured_data": {},
        "confidence": None,
        "model": {
            "name": "vision_llama",
            "version": "0.1.0",
        },
        "warnings": [],
        "error": None,
        "service_time_ms": 1,
    }


def test_vision_request_accepts_contract_shape() -> None:
    request = VisionRequest.model_validate(valid_vision_request())

    assert request.recognition_task == "chart"
    assert request.requested_format == "none"


def test_vision_request_rejects_invalid_bbox() -> None:
    payload = valid_vision_request()
    payload["bbox"] = [10, 20, 10, 120]

    with pytest.raises(ValidationError):
        VisionRequest.model_validate(payload)


def test_vision_response_accepts_contract_shape() -> None:
    response = VisionResponse.model_validate(valid_vision_response())

    assert response.status == "completed"
    assert response.visual_type == "chart_or_plot"


def test_failed_vision_response_requires_error() -> None:
    payload = valid_vision_response()
    payload["status"] = "failed"

    with pytest.raises(ValidationError):
        VisionResponse.model_validate(payload)
