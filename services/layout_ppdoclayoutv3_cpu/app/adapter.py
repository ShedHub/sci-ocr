from shared.contracts.layout import LayoutBlockType


PPDOCLAYOUTV3_LABEL_TO_CANONICAL: dict[str, LayoutBlockType] = {
    "abstract": "text",
    "algorithm": "text",
    "aside_text": "text",
    "chart": "figure",
    "content": "text",
    "display_formula": "formula",
    "doc_title": "title",
    "figure_title": "text",
    "footer": "text",
    "footer_image": "figure",
    "footnote": "text",
    "formula_number": "formula",
    "header": "text",
    "header_image": "figure",
    "image": "figure",
    "inline_formula": "formula",
    "number": "text",
    "paragraph_title": "title",
    "reference": "text",
    "reference_content": "text",
    "seal": "figure",
    "table": "table",
    "text": "text",
    "vertical_text": "text",
    "vision_footnote": "text",
}


def map_label_to_canonical(label: str) -> LayoutBlockType:
    try:
        return PPDOCLAYOUTV3_LABEL_TO_CANONICAL[label]
    except KeyError as exc:
        raise ValueError(f"Unsupported PP-DocLayoutV3 label: {label}") from exc
