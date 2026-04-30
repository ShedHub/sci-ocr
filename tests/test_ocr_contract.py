import pytest
from pydantic import ValidationError

from shared.contracts.ocr import OcrJobStartResponse, OcrJobStatusResponse, OcrRequest, OcrResponse


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


def test_ocr_job_start_response_accepts_contract_shape() -> None:
    response = OcrJobStartResponse.model_validate(
        {
            "status": "queued",
            "task_id": "task-1",
            "job_id": "job-1",
            "page_number": 1,
            "block_id": "p1_b1",
            "submitted_at": "2026-04-30T12:00:00+00:00",
        }
    )

    assert response.task_id == "task-1"


def test_completed_ocr_job_status_requires_result() -> None:
    payload = {
        "task_id": "task-1",
        "status": "completed",
        "stage": "completed",
        "job_id": "job-1",
        "page_number": 1,
        "block_id": "p1_b1",
        "submitted_at": "2026-04-30T12:00:00+00:00",
        "last_heartbeat_at": "2026-04-30T12:00:01+00:00",
        "elapsed_seconds": 1,
    }

    with pytest.raises(ValidationError):
        OcrJobStatusResponse.model_validate(payload)


def test_running_ocr_job_status_accepts_heartbeat() -> None:
    response = OcrJobStatusResponse.model_validate(
        {
            "task_id": "task-1",
            "status": "running",
            "stage": "generating",
            "job_id": "job-1",
            "page_number": 1,
            "block_id": "p1_b1",
            "submitted_at": "2026-04-30T12:00:00+00:00",
            "started_at": "2026-04-30T12:00:00+00:00",
            "last_heartbeat_at": "2026-04-30T12:00:01+00:00",
            "elapsed_seconds": 1.0,
            "message": "model.generate is still running",
        }
    )

    assert response.status == "running"
