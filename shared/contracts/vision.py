"""
Pydantic schemas for the vision worker service boundary.

The vision service receives one cropped visual block and returns Markdown-ready
content for final article assembly.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


VisionStatus = Literal["completed", "degraded", "failed"]
VisionRecognitionTask = Literal["image", "chart"]
VisionOutputFormat = Literal["markdown", "mermaid", "none"]
VisionVisualType = Literal[
    "photo_or_illustration",
    "chart_or_plot",
    "diagram_or_flowchart",
    "table_like_visual",
    "unknown",
]


class VisionReadyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready"]
    service: str = Field(min_length=1)
    model: str = Field(min_length=1)
    version: str = Field(min_length=1)


class VisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    document_id: str | None = None
    page_number: int = Field(ge=1)
    block_id: str = Field(min_length=1)
    block_type: str = Field(min_length=1)
    layout_label: str | None = None
    content_role: str = Field(min_length=1)
    recognition_task: VisionRecognitionTask
    requested_format: Literal["none"]
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


class VisionModelInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    backend: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: VisionStatus
    job_id: str = Field(min_length=1)
    document_id: str | None = None
    page_number: int = Field(ge=1)
    block_id: str = Field(min_length=1)
    content_role: str = Field(min_length=1)
    recognition_task: VisionRecognitionTask
    visual_type: VisionVisualType
    format: VisionOutputFormat
    content: str = ""
    structured_data: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    model: VisionModelInfo
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    service_time_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_status_payload(self):
        if self.status == "failed" and not self.error:
            raise ValueError("failed vision responses must include error")
        if self.status in {"completed", "degraded"} and self.error is not None:
            raise ValueError("successful vision responses must not include error")
        return self


class NormalizedVisionBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    document_id: str | None = None
    page_number: int = Field(ge=1)
    block_id: str = Field(min_length=1)
    block_type: str = Field(min_length=1)
    layout_label: str | None = None
    content_role: str = Field(min_length=1)
    recognition_task: VisionRecognitionTask
    visual_type: VisionVisualType
    format: VisionOutputFormat
    content: str
    structured_data: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    bbox: tuple[float, float, float, float]
    order: int = Field(ge=1)
    image_path: str = Field(min_length=1)
    source: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)


class NormalizedVisionArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: Literal["vision"]
    status: VisionStatus
    source: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    document_id: str | None = None
    page_number: int = Field(ge=1)
    blocks: list[NormalizedVisionBlock] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
