"""
Route layout blocks to downstream worker services.

Layout detection answers "what is on the page and where". This module answers
"who should process this block next, and which output format do we expect".
"""

from dataclasses import asdict, dataclass
from typing import Literal


TargetService = Literal["ocr", "vision", "skip"]
RecognitionTask = Literal["text", "table", "formula", "image", "chart", "none"]
RequestedFormat = Literal["markdown", "latex", "none"]


@dataclass(frozen=True)
class BlockRoute:
    target_service: TargetService
    recognition_task: RecognitionTask
    requested_format: RequestedFormat
    content_role: str
    route_reason: str

    def model_dump(self) -> dict[str, str]:
        return asdict(self)


OCR_TEXT_ROUTE = BlockRoute(
    target_service="ocr",
    recognition_task="text",
    requested_format="markdown",
    content_role="text",
    route_reason="text-like layout block",
)

OCR_TABLE_ROUTE = BlockRoute(
    target_service="ocr",
    recognition_task="table",
    requested_format="markdown",
    content_role="table",
    route_reason="table layout block",
)

OCR_FORMULA_ROUTE = BlockRoute(
    target_service="ocr",
    recognition_task="formula",
    requested_format="latex",
    content_role="formula",
    route_reason="formula layout block",
)

VISION_IMAGE_ROUTE = BlockRoute(
    target_service="vision",
    recognition_task="image",
    requested_format="none",
    content_role="image",
    route_reason="image-like layout block for future vision service",
)

VISION_CHART_ROUTE = BlockRoute(
    target_service="vision",
    recognition_task="chart",
    requested_format="none",
    content_role="chart",
    route_reason="chart layout block for future chart service",
)


PPDOCLAYOUTV3_LABEL_ROUTES: dict[str, BlockRoute] = {
    "abstract": BlockRoute("ocr", "text", "markdown", "abstract", "abstract text"),
    "algorithm": BlockRoute("ocr", "text", "markdown", "algorithm", "algorithm text"),
    "aside_text": BlockRoute("ocr", "text", "markdown", "aside", "aside text"),
    "chart": VISION_CHART_ROUTE,
    "content": BlockRoute("ocr", "text", "markdown", "paragraph", "content text"),
    "display_formula": BlockRoute(
        "ocr",
        "formula",
        "latex",
        "formula",
        "display formula",
    ),
    "doc_title": BlockRoute("ocr", "text", "markdown", "title", "document title"),
    "figure_title": BlockRoute("ocr", "text", "markdown", "caption", "figure caption"),
    "footer": BlockRoute("ocr", "text", "markdown", "footer", "page footer"),
    "footer_image": BlockRoute(
        "vision",
        "image",
        "none",
        "footer_image",
        "footer image for future vision service",
    ),
    "footnote": BlockRoute("ocr", "text", "markdown", "footnote", "footnote text"),
    "formula_number": BlockRoute(
        "ocr",
        "formula",
        "latex",
        "formula_number",
        "formula number or formula-adjacent block",
    ),
    "header": BlockRoute("ocr", "text", "markdown", "header", "page header"),
    "header_image": BlockRoute(
        "vision",
        "image",
        "none",
        "header_image",
        "header image for future vision service",
    ),
    "image": VISION_IMAGE_ROUTE,
    "inline_formula": BlockRoute(
        "ocr",
        "formula",
        "latex",
        "inline_formula",
        "inline formula",
    ),
    "number": BlockRoute("ocr", "text", "markdown", "page_number", "page number"),
    "paragraph_title": BlockRoute(
        "ocr",
        "text",
        "markdown",
        "heading",
        "paragraph or section heading",
    ),
    "reference": BlockRoute("ocr", "text", "markdown", "reference", "reference label"),
    "reference_content": BlockRoute(
        "ocr",
        "text",
        "markdown",
        "reference",
        "reference content",
    ),
    "seal": BlockRoute("ocr", "text", "markdown", "seal", "seal may contain text"),
    "table": OCR_TABLE_ROUTE,
    "text": OCR_TEXT_ROUTE,
    "vertical_text": BlockRoute(
        "ocr",
        "text",
        "markdown",
        "vertical_text",
        "vertical text",
    ),
    "vision_footnote": BlockRoute(
        "ocr",
        "text",
        "markdown",
        "footnote",
        "vision footnote text",
    ),
}


CANONICAL_LAYOUT_TYPE_ROUTES: dict[str, BlockRoute] = {
    "title": BlockRoute("ocr", "text", "markdown", "title", "canonical title block"),
    "text": OCR_TEXT_ROUTE,
    "table": OCR_TABLE_ROUTE,
    "formula": OCR_FORMULA_ROUTE,
    "figure": VISION_IMAGE_ROUTE,
}


def route_layout_label(layout_label: str) -> BlockRoute:
    """
    Route a native backend label, preferably from PP-DocLayoutV3.
    """
    try:
        return PPDOCLAYOUTV3_LABEL_ROUTES[layout_label]
    except KeyError as exc:
        raise ValueError(f"Unsupported layout label for routing: {layout_label}") from exc


def route_canonical_layout_type(layout_type: str) -> BlockRoute:
    """
    Route the current normalized layout type when the native label is absent.
    """
    try:
        return CANONICAL_LAYOUT_TYPE_ROUTES[layout_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported canonical layout type for routing: {layout_type}") from exc


def route_layout_block(block: dict) -> dict:
    """
    Attach routing information to one layout block.

    Prefer the source backend label when available because it preserves detail
    such as `figure_title` versus `image`. Fall back to the current canonical
    `type` field for existing normalized layout artifacts.
    """
    layout_label = block.get("layout_label") or block.get("source_label")
    route = (
        route_layout_label(layout_label)
        if layout_label
        else route_canonical_layout_type(block["type"])
    )
    return {
        **block,
        "routing": route.model_dump(),
    }


def route_layout_blocks(blocks: list[dict]) -> list[dict]:
    return [route_layout_block(block) for block in blocks]
