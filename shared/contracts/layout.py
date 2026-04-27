"""
Pydantic schemas for the layout service boundary.

These models describe the stable HTTP contract between the orchestrator and any
layout backend. The current backend is layout_stub; a future PP-DocLayoutV3
service should implement the same request and response shapes.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


LayoutStatus = Literal["completed", "degraded", "failed"]
LayoutBlockType = Literal["title", "text", "table", "formula", "figure"]


class LayoutReadyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready"]
    service: str = Field(min_length=1)
    model: str = Field(min_length=1)
    version: str = Field(min_length=1)


class LayoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    document_id: str | None = None
    page_number: int = Field(ge=1)
    image_path: str = Field(min_length=1)


class LayoutModelInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    backend: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LayoutImageInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    dpi: int | None = Field(default=None, gt=0)


class LayoutBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str = Field(min_length=1)
    type: LayoutBlockType
    bbox: tuple[float, float, float, float]
    confidence: float = Field(ge=0.0, le=1.0)
    order: int = Field(ge=1)

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, bbox: tuple[float, float, float, float]):
        x1, y1, x2, y2 = bbox
        if x2 <= x1 or y2 <= y1:
            raise ValueError("bbox must be [x1, y1, x2, y2] with x2 > x1 and y2 > y1")
        return bbox


class LayoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: LayoutStatus
    job_id: str = Field(min_length=1)
    document_id: str | None = None
    page_number: int = Field(ge=1)
    model: LayoutModelInfo
    image: LayoutImageInfo
    blocks: list[LayoutBlock] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    service_time_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_status_payload(self):
        if self.status == "failed" and not self.error:
            raise ValueError("failed layout responses must include error")
        if self.status in {"completed", "degraded"} and self.error is not None:
            raise ValueError("successful layout responses must not include error")
        return self


class NormalizedLayoutBlock(LayoutBlock):
    source: str = Field(min_length=1)


class NormalizedLayoutArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: Literal["layout"]
    status: LayoutStatus
    source: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    document_id: str | None = None
    page_number: int = Field(ge=1)
    image: LayoutImageInfo
    blocks: list[NormalizedLayoutBlock] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
