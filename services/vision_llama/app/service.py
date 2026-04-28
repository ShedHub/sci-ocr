import base64
import os
import re
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from shared.contracts.vision import (
    VisionReadyResponse,
    VisionRequest,
    VisionResponse,
    VisionVisualType,
)


SERVICE_NAME = "vision_llama"
MODEL_NAME = os.getenv("VISION_MODEL_NAME", "qwen3.6-27b-q4_k_m")
MODEL_VERSION = os.getenv("VISION_MODEL_VERSION", "local-gguf")
DEFAULT_LLAMA_SERVER_URL = "http://127.0.0.1:8080"
DEFAULT_TIMEOUT_SECONDS = 1200.0

VISUAL_TYPES: tuple[VisionVisualType, ...] = (
    "photo_or_illustration",
    "chart_or_plot",
    "diagram_or_flowchart",
    "table_like_visual",
    "unknown",
)


class VisionLlamaUnavailable(RuntimeError):
    """Raised when llama-server cannot process a vision request."""


def get_llama_server_url() -> str:
    return os.getenv("LLAMA_SERVER_URL", DEFAULT_LLAMA_SERVER_URL).rstrip("/")


def get_timeout_seconds() -> float:
    return float(os.getenv("LLAMA_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))


def get_status() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


def get_ready() -> VisionReadyResponse:
    url = f"{get_llama_server_url()}/health"
    try:
        response = httpx.get(url, timeout=10, trust_env=False)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise VisionLlamaUnavailable(f"llama-server is not ready at {url}: {exc}") from exc

    return VisionReadyResponse(
        status="ready",
        service=SERVICE_NAME,
        model=MODEL_NAME,
        version=MODEL_VERSION,
    )


def validate_crop_path(image_path: str) -> Path:
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"image_path does not exist or is not a file: {image_path}")
    return path


def image_data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_prompt(request: VisionRequest) -> str:
    return f"""
You are processing a cropped visual block from a scientific PDF article.
/no_think

Block metadata:
- page_number: {request.page_number}
- block_id: {request.block_id}
- layout_label: {request.layout_label or "unknown"}
- routed_task: {request.recognition_task}
- content_role: {request.content_role}

Classify the visual block as exactly one of:
- photo_or_illustration
- chart_or_plot
- diagram_or_flowchart
- table_like_visual
- unknown

Return Markdown only.
Keep the response concise: no more than 220 words unless Mermaid is necessary.

Start with this exact line:
Visual type: <one classification>

Then produce the useful article content:
- If photo_or_illustration: write a detailed scientific description of what is visible.
- If chart_or_plot: describe axes, legend, series, trends, and extract approximate data as a Markdown table when possible. Mark approximate data clearly.
- If diagram_or_flowchart: reconstruct the diagram as Mermaid when possible, then add a concise explanation.
- If table_like_visual: extract the content as Markdown table when possible.
- If unknown: provide the best useful description and state uncertainty.

Do not mention that you are an AI model. Do not wrap the whole answer in a code fence.
""".strip()


def build_chat_payload(request: VisionRequest, image_path: Path) -> dict[str, Any]:
    return {
        "model": MODEL_NAME,
        "temperature": float(os.getenv("LLAMA_TEMPERATURE", "0.1")),
        "max_tokens": int(os.getenv("LLAMA_MAX_TOKENS", "512")),
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": build_prompt(request)},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_data_url(image_path)},
                    },
                ],
            }
        ],
    }


def call_llama_server(request: VisionRequest, image_path: Path) -> str:
    url = f"{get_llama_server_url()}/v1/chat/completions"
    try:
        response = httpx.post(
            url,
            json=build_chat_payload(request, image_path),
            timeout=get_timeout_seconds(),
            trust_env=False,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise VisionLlamaUnavailable(
            f"llama-server vision request failed with HTTP "
            f"{exc.response.status_code}: {exc.response.text}"
        ) from exc
    except (httpx.RequestError, ValueError) as exc:
        raise VisionLlamaUnavailable(f"llama-server vision request failed: {exc}") from exc

    try:
        message = payload["choices"][0]["message"]
        content = message.get("content") or message.get("reasoning_content") or ""
        return content.strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise VisionLlamaUnavailable(f"unexpected llama-server response: {payload}") from exc


def parse_visual_type(content: str, fallback: VisionVisualType) -> VisionVisualType:
    first_line = content.strip().splitlines()[0] if content.strip() else ""
    match = re.match(r"visual\s+type\s*:\s*([a-z_]+)", first_line, flags=re.IGNORECASE)
    if not match:
        return fallback

    value = match.group(1).lower()
    return value if value in VISUAL_TYPES else fallback


def infer_fallback_visual_type(request: VisionRequest) -> VisionVisualType:
    if request.recognition_task == "chart" or request.content_role == "chart":
        return "chart_or_plot"
    return "unknown"


def build_empty_output_fallback(request: VisionRequest) -> str:
    return (
        f"Visual type: {infer_fallback_visual_type(request)}\n\n"
        f"[Vision output empty for {request.block_id}; inspect the crop artifact.]"
    )


def run_vision(request: VisionRequest) -> VisionResponse:
    started = perf_counter()
    image_path = validate_crop_path(request.image_path)
    content = call_llama_server(request, image_path)
    warnings: list[str] = []
    status = "completed"
    if not content.strip():
        content = build_empty_output_fallback(request)
        warnings.append("llama-server returned an empty vision response")
        status = "degraded"
    fallback_visual_type = infer_fallback_visual_type(request)

    return VisionResponse(
        status=status,
        job_id=request.job_id,
        document_id=request.document_id,
        page_number=request.page_number,
        block_id=request.block_id,
        content_role=request.content_role,
        recognition_task=request.recognition_task,
        visual_type=parse_visual_type(content, fallback_visual_type),
        format="markdown",
        content=content,
        structured_data={},
        confidence=None,
        model={
            "name": MODEL_NAME,
            "version": MODEL_VERSION,
            "backend": SERVICE_NAME,
            "metadata": {
                "llama_server_url": get_llama_server_url(),
            },
        },
        warnings=warnings,
        error=None,
        service_time_ms=int((perf_counter() - started) * 1000),
    )
