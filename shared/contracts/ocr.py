"""
Pydantic schemas for the OCR worker service boundary.

The OCR service receives one cropped layout block and returns recognized content
in the format requested by the orchestrator.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


OcrStatus = Literal["completed", "degraded", "failed"]
OcrJobStatus = Literal["queued", "running", "completed", "failed", "stalled"]
OcrRecognitionTask = Literal["text", "table", "formula"]
OcrOutputFormat = Literal["markdown", "latex"]


class OcrReadyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready"]
    service: str = Field(min_length=1)
    model: str = Field(min_length=1)
    version: str = Field(min_length=1)


class OcrRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    document_id: str | None = None
    page_number: int = Field(ge=1)
    block_id: str = Field(min_length=1)
    block_type: str = Field(min_length=1)
    layout_label: str | None = None
    content_role: str = Field(min_length=1)
    recognition_task: OcrRecognitionTask
    requested_format: OcrOutputFormat
    image_path: str = Field(min_length=1)
    bbox: tuple[float, float, float, float]
    order: int = Field(ge=1)

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, bbox: tuple[float, float, float, float]):
        x1, y1, x2, y2 = bbox
        if x2 <= x1 or y2 <= y1:
            raise ValueError("bbox must be [x1, y1, x2, y2] with x2 > x1 and y2 > y1")
        return bbox

    @model_validator(mode="after")
    def validate_task_format(self):
        if self.recognition_task == "formula" and self.requested_format != "latex":
            raise ValueError("formula OCR requests must use requested_format='latex'")
        if self.recognition_task in {"text", "table"} and self.requested_format != "markdown":
            raise ValueError("text and table OCR requests must use requested_format='markdown'")
        return self


class OcrModelInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    backend: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OcrResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OcrStatus
    job_id: str = Field(min_length=1)
    document_id: str | None = None
    page_number: int = Field(ge=1)
    block_id: str = Field(min_length=1)
    content_role: str = Field(min_length=1)
    recognition_task: OcrRecognitionTask
    format: OcrOutputFormat
    content: str = ""
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    model: OcrModelInfo
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    service_time_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_status_payload(self):
        if self.status == "failed" and not self.error:
            raise ValueError("failed OCR responses must include error")
        if self.status in {"completed", "degraded"} and self.error is not None:
            raise ValueError("successful OCR responses must not include error")
        return self


class OcrJobStartResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["queued"]
    task_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    block_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class OcrJobStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1)
    status: OcrJobStatus
    stage: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    document_id: str | None = None
    page_number: int = Field(ge=1)
    block_id: str = Field(min_length=1)
    started_at: str | None = None
    submitted_at: str = Field(min_length=1)
    completed_at: str | None = None
    last_heartbeat_at: str = Field(min_length=1)
    elapsed_seconds: float = Field(ge=0)
    message: str = ""
    result: OcrResponse | None = None
    error: str | None = None

    @model_validator(mode="after")
    def validate_terminal_payload(self):
        if self.status == "completed" and self.result is None:
            raise ValueError("completed OCR jobs must include result")
        if self.status in {"failed", "stalled"} and not self.error:
            raise ValueError("failed or stalled OCR jobs must include error")
        return self


class NormalizedOcrBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    document_id: str | None = None
    page_number: int = Field(ge=1)
    block_id: str = Field(min_length=1)
    block_type: str = Field(min_length=1)
    layout_label: str | None = None
    content_role: str = Field(min_length=1)
    recognition_task: OcrRecognitionTask
    format: OcrOutputFormat
    content: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    bbox: tuple[float, float, float, float]
    order: int = Field(ge=1)
    image_path: str = Field(min_length=1)
    source: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)


class NormalizedOcrArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: Literal["ocr"]
    status: OcrStatus
    source: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    document_id: str | None = None
    page_number: int = Field(ge=1)
    blocks: list[NormalizedOcrBlock] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
