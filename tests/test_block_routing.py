import pytest

from orchestrator.app.block_routing import (
    route_canonical_layout_type,
    route_layout_label,
)


def test_routes_text_like_layout_labels_to_ocr_markdown() -> None:
    route = route_layout_label("figure_title")

    assert route.target_service == "ocr"
    assert route.recognition_task == "text"
    assert route.requested_format == "markdown"
    assert route.content_role == "caption"


def test_routes_tables_to_ocr_markdown() -> None:
    route = route_layout_label("table")

    assert route.target_service == "ocr"
    assert route.recognition_task == "table"
    assert route.requested_format == "markdown"


def test_routes_formulas_to_ocr_latex() -> None:
    route = route_layout_label("display_formula")

    assert route.target_service == "ocr"
    assert route.recognition_task == "formula"
    assert route.requested_format == "latex"


def test_routes_images_and_charts_to_future_vision_service() -> None:
    image_route = route_layout_label("image")
    chart_route = route_layout_label("chart")

    assert image_route.target_service == "vision"
    assert image_route.recognition_task == "image"
    assert chart_route.target_service == "vision"
    assert chart_route.recognition_task == "chart"


def test_routes_current_canonical_layout_types() -> None:
    assert route_canonical_layout_type("text").target_service == "ocr"
    assert route_canonical_layout_type("table").recognition_task == "table"
    assert route_canonical_layout_type("formula").requested_format == "latex"
    assert route_canonical_layout_type("figure").target_service == "vision"


def test_rejects_unknown_labels() -> None:
    with pytest.raises(ValueError):
        route_layout_label("unexpected_label")
