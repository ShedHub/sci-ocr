import pytest
from pydantic import ValidationError

from shared.contracts.layout import LayoutRequest, LayoutResponse


def valid_layout_response() -> dict:
    return {
        "status": "completed",
        "job_id": "job-1",
        "document_id": "doc.pdf",
        "page_number": 1,
        "model": {
            "name": "layout_stub",
            "version": "0.1.0",
        },
        "image": {
            "path": "/app/jobs/output/job-1/assets/pages/page_0001.png",
            "width": 1000,
            "height": 1400,
        },
        "blocks": [
            {
                "block_id": "p1_b1",
                "type": "text",
                "layout_label": "content",
                "bbox": [100, 100, 700, 180],
                "confidence": 0.98,
                "order": 1,
            }
        ],
        "warnings": [],
        "error": None,
        "service_time_ms": 12,
    }


def test_layout_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        LayoutRequest.model_validate(
            {
                "job_id": "job-1",
                "page_number": 1,
                "image_path": "/tmp/page.png",
                "backend_specific_toggle": True,
            }
        )


def test_layout_response_accepts_contract_shape() -> None:
    response = LayoutResponse.model_validate(valid_layout_response())

    assert response.status == "completed"
    assert response.blocks[0].type == "text"
    assert response.blocks[0].layout_label == "content"


def test_layout_response_rejects_unknown_block_type() -> None:
    payload = valid_layout_response()
    payload["blocks"][0]["type"] = "pp_table_label"

    with pytest.raises(ValidationError):
        LayoutResponse.model_validate(payload)


def test_layout_response_rejects_invalid_bbox() -> None:
    payload = valid_layout_response()
    payload["blocks"][0]["bbox"] = [700, 100, 100, 180]

    with pytest.raises(ValidationError):
        LayoutResponse.model_validate(payload)


def test_failed_layout_response_requires_error() -> None:
    payload = valid_layout_response()
    payload["status"] = "failed"

    with pytest.raises(ValidationError):
        LayoutResponse.model_validate(payload)
