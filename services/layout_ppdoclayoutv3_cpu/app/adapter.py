from shared.contracts.layout import LayoutBlockType


PPDOCLAYOUTV3_LABELS: tuple[str, ...] = (
    "abstract",
    "algorithm",
    "aside_text",
    "chart",
    "content",
    "display_formula",
    "doc_title",
    "figure_title",
    "footer",
    "footer_image",
    "footnote",
    "formula_number",
    "header",
    "header_image",
    "image",
    "inline_formula",
    "number",
    "paragraph_title",
    "reference",
    "reference_content",
    "seal",
    "table",
    "text",
    "vertical_text",
    "vision_footnote",
)


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


def validate_label_mapping(labels: tuple[str, ...] = PPDOCLAYOUTV3_LABELS) -> None:
    """
    Fail fast if the local model label set and adapter mapping drift apart.
    """
    expected = set(labels)
    mapped = set(PPDOCLAYOUTV3_LABEL_TO_CANONICAL)
    missing = sorted(expected - mapped)
    extra = sorted(mapped - expected)

    if missing or extra:
        details = []
        if missing:
            details.append(f"missing mappings: {', '.join(missing)}")
        if extra:
            details.append(f"unknown mappings: {', '.join(extra)}")
        raise ValueError("PP-DocLayoutV3 label mapping is incomplete: " + "; ".join(details))


def map_label_to_canonical(label: str) -> LayoutBlockType:
    try:
        return PPDOCLAYOUTV3_LABEL_TO_CANONICAL[label]
    except KeyError as exc:
        raise ValueError(f"Unsupported PP-DocLayoutV3 label: {label}") from exc
