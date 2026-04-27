import pytest

from services.layout_ppdoclayoutv3_cpu.app.adapter import (
    PPDOCLAYOUTV3_LABELS,
    PPDOCLAYOUTV3_LABEL_TO_CANONICAL,
    map_label_to_canonical,
    validate_label_mapping,
)


def test_ppdoclayoutv3_label_mapping() -> None:
    assert map_label_to_canonical("doc_title") == "title"
    assert map_label_to_canonical("display_formula") == "formula"
    assert map_label_to_canonical("table") == "table"
    assert map_label_to_canonical("image") == "figure"
    assert map_label_to_canonical("text") == "text"


def test_ppdoclayoutv3_label_mapping_rejects_unknown_labels() -> None:
    with pytest.raises(ValueError):
        map_label_to_canonical("unexpected_backend_label")


def test_ppdoclayoutv3_label_mapping_covers_declared_labels() -> None:
    validate_label_mapping()

    assert set(PPDOCLAYOUTV3_LABEL_TO_CANONICAL) == set(PPDOCLAYOUTV3_LABELS)
