import pytest

from services.layout_ppdoclayoutv3_cpu.app.adapter import map_label_to_canonical


def test_ppdoclayoutv3_label_mapping() -> None:
    assert map_label_to_canonical("doc_title") == "title"
    assert map_label_to_canonical("display_formula") == "formula"
    assert map_label_to_canonical("table") == "table"
    assert map_label_to_canonical("image") == "figure"
    assert map_label_to_canonical("text") == "text"


def test_ppdoclayoutv3_label_mapping_rejects_unknown_labels() -> None:
    with pytest.raises(ValueError):
        map_label_to_canonical("unexpected_backend_label")
