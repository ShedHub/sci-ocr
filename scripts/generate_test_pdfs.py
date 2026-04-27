"""
Generate representative PDF fixtures for pipeline testing.

The fixtures intentionally use PyMuPDF and Pillow instead of a TeX compiler so
they can be regenerated in a plain Python test environment.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import fitz
from PIL import Image, ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "tests" / "fixtures" / "pdfs"


def _insert_heading(page: fitz.Page, text: str, y: float) -> None:
    page.insert_text((54, y), text, fontsize=18, fontname="helv", color=(0.05, 0.12, 0.28))


def _insert_paragraph(page: fitz.Page, text: str, rect: fitz.Rect) -> None:
    page.insert_textbox(rect, text, fontsize=10.5, fontname="helv", lineheight=1.25)


def _draw_table(page: fitz.Page, rect: fitz.Rect, headers: list[str], rows: list[list[str]]) -> None:
    row_count = len(rows) + 1
    col_count = len(headers)
    row_h = rect.height / row_count
    col_w = rect.width / col_count

    page.draw_rect(rect, color=(0, 0, 0), width=0.8)
    for row in range(1, row_count):
        y = rect.y0 + row * row_h
        page.draw_line((rect.x0, y), (rect.x1, y), color=(0, 0, 0), width=0.6)
    for col in range(1, col_count):
        x = rect.x0 + col * col_w
        page.draw_line((x, rect.y0), (x, rect.y1), color=(0, 0, 0), width=0.6)

    for col, header in enumerate(headers):
        cell = fitz.Rect(rect.x0 + col * col_w + 6, rect.y0 + 7, rect.x0 + (col + 1) * col_w - 6, rect.y0 + row_h)
        page.insert_textbox(cell, header, fontsize=9.5, fontname="helv", color=(0.02, 0.10, 0.22))

    for row_index, row_values in enumerate(rows, start=1):
        for col, value in enumerate(row_values):
            cell = fitz.Rect(
                rect.x0 + col * col_w + 6,
                rect.y0 + row_index * row_h + 7,
                rect.x0 + (col + 1) * col_w - 6,
                rect.y0 + (row_index + 1) * row_h,
            )
            page.insert_textbox(cell, value, fontsize=9.2, fontname="helv")


def _render_formula_asset(path: Path, formula: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure = plt.figure(figsize=(7.2, 0.55), dpi=220)
    figure.patch.set_alpha(0.0)
    figure.text(0.01, 0.52, formula, fontsize=22, va="center", ha="left")
    figure.savefig(path, transparent=True, bbox_inches="tight", pad_inches=0.06)
    plt.close(figure)


def _draw_formula_box(page: fitz.Page, rect: fitz.Rect, formulas: list[str]) -> None:
    page.draw_rect(rect, color=(0.38, 0.18, 0.68), width=0.8)
    page.insert_text((rect.x0 + 10, rect.y0 + 18), "Formula block", fontsize=9.5, fontname="helv", color=(0.38, 0.18, 0.68))
    y = rect.y0 + 32
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for index, formula in enumerate(formulas, start=1):
            formula_path = tmp_path / f"formula_{index}.png"
            _render_formula_asset(formula_path, formula)
            page.insert_image(
                fitz.Rect(rect.x0 + 18, y, rect.x1 - 18, y + 28),
                filename=str(formula_path),
                keep_proportion=True,
            )
            y += 34


def _create_photo_asset(path: Path) -> None:
    image = Image.new("RGB", (520, 260), "#edf2f7")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 190, 520, 260), fill="#b7d7a8")
    draw.rectangle((30, 85, 170, 190), fill="#7aa6c2")
    draw.polygon([(235, 190), (330, 55), (430, 190)], fill="#8e9aaf")
    draw.ellipse((370, 25, 430, 85), fill="#f2c94c")
    draw.text((28, 22), "Embedded image placeholder", fill="#102a43")
    image.save(path)


def _create_bar_chart_asset(path: Path) -> None:
    image = Image.new("RGB", (560, 320), "white")
    draw = ImageDraw.Draw(image)
    left, top, right, bottom = 58, 34, 520, 270
    draw.line((left, bottom, right, bottom), fill="#111827", width=3)
    draw.line((left, bottom, left, top), fill="#111827", width=3)
    values = [35, 82, 58, 118, 96]
    labels = ["A", "B", "C", "D", "E"]
    bar_w = 58
    gap = 30
    for index, value in enumerate(values):
        x0 = left + 34 + index * (bar_w + gap)
        y0 = bottom - value * 1.55
        draw.rectangle((x0, y0, x0 + bar_w, bottom), fill="#2f80ed")
        draw.text((x0 + 18, bottom + 10), labels[index], fill="#111827")
        draw.text((x0 + 13, y0 - 20), str(value), fill="#111827")
    draw.text((170, 8), "Chart: Synthetic extraction benchmark", fill="#111827")
    image.save(path)


def _create_line_chart_asset(path: Path) -> None:
    image = Image.new("RGB", (560, 320), "white")
    draw = ImageDraw.Draw(image)
    left, top, right, bottom = 62, 34, 520, 270

    for step in range(5):
        y = bottom - step * 48
        draw.line((left, y, right, y), fill="#e5e7eb", width=1)
    for step in range(6):
        x = left + step * 76
        draw.line((x, top, x, bottom), fill="#f3f4f6", width=1)

    draw.line((left, bottom, right, bottom), fill="#111827", width=3)
    draw.line((left, bottom, left, top), fill="#111827", width=3)
    points = [
        (left, bottom - 22),
        (left + 72, bottom - 58),
        (left + 150, bottom - 76),
        (left + 226, bottom - 138),
        (left + 312, bottom - 112),
        (left + 398, bottom - 185),
        (right, bottom - 210),
    ]
    draw.line(points, fill="#d62728", width=4)
    for point in points:
        x, y = point
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill="#d62728")

    draw.text((170, 8), "Classic line graph: response over time", fill="#111827")
    draw.text((250, 292), "time", fill="#111827")
    draw.text((10, 132), "response", fill="#111827")
    image.save(path)


def create_science_mixed_pdf(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()

    page = document.new_page(width=612, height=792)
    _insert_heading(page, "SCI-OCR Mixed Content Fixture", 54)
    _insert_paragraph(
        page,
        (
            "This page combines section headings, dense prose, a data table, "
            "and rendered mathematical notation. It is designed to exercise "
            "layout routing before a real OCR backend is available."
        ),
        fitz.Rect(54, 82, 558, 145),
    )
    _insert_heading(page, "1. Methods", 172)
    _insert_paragraph(
        page,
        (
            "The synthetic experiment contains repeated visual structures and "
            "controlled vocabulary so that future OCR output can be compared "
            "against stable expectations without using private documents."
        ),
        fitz.Rect(54, 198, 558, 255),
    )
    _draw_table(
        page,
        fitz.Rect(54, 280, 558, 410),
        ["Sample", "Temperature", "Yield", "Notes"],
        [
            ["A-01", "21 C", "78%", "baseline"],
            ["B-02", "37 C", "91%", "heated"],
            ["C-03", "42 C", "88%", "replicate"],
        ],
    )
    _draw_formula_box(
        page,
        fitz.Rect(54, 448, 558, 585),
        [
            r"$E = mc^2$",
            r"$a^2 + b^2 = c^2$",
            r"$\int_0^\infty e^{-x^2}\,dx = \frac{\sqrt{\pi}}{2}$",
        ],
    )
    _insert_paragraph(
        page,
        "Reference-like footer text: Doe et al. 2026, Synthetic Document Benchmarks.",
        fitz.Rect(54, 710, 558, 742),
    )

    page = document.new_page(width=612, height=792)
    _insert_heading(page, "2. Visual Regions", 54)
    _insert_paragraph(
        page,
        (
            "This second page contains an embedded image and a simple chart. "
            "The current pipeline should route these regions to the future "
            "vision worker instead of sending them to OCR."
        ),
        fitz.Rect(54, 82, 558, 140),
    )

    with TemporaryDirectory() as tmp_dir:
        photo_path = Path(tmp_dir) / "photo.png"
        bar_chart_path = Path(tmp_dir) / "bar_chart.png"
        line_chart_path = Path(tmp_dir) / "line_chart.png"
        _create_photo_asset(photo_path)
        _create_bar_chart_asset(bar_chart_path)
        _create_line_chart_asset(line_chart_path)

        page.insert_image(fitz.Rect(54, 156, 558, 356), filename=str(photo_path))
        page.insert_text((54, 376), "Figure 1. Embedded synthetic image for future vision tests.", fontsize=10, fontname="helv")
        page.insert_image(fitz.Rect(54, 410, 300, 580), filename=str(bar_chart_path))
        page.insert_text((54, 600), "Chart 1. Synthetic extraction benchmark with five bars.", fontsize=10, fontname="helv")
        page.insert_image(fitz.Rect(312, 410, 558, 580), filename=str(line_chart_path))
        page.insert_text((312, 600), "Chart 2. Classic line graph with axes and curve.", fontsize=10, fontname="helv")

    document.save(output_path)
    document.close()


def create_formula_table_pdf(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    page = document.new_page(width=612, height=792)

    _insert_heading(page, "SCI-OCR Formula and Table Fixture", 54)
    _insert_paragraph(
        page,
        (
            "A compact one-page fixture with text, a table, and three displayed "
            "formula lines. Use it for quick local smoke checks."
        ),
        fitz.Rect(54, 82, 558, 135),
    )
    _draw_table(
        page,
        fitz.Rect(54, 168, 558, 312),
        ["Metric", "Run 1", "Run 2", "Delta"],
        [
            ["Accuracy", "0.82", "0.91", "+0.09"],
            ["Latency", "145 ms", "132 ms", "-13 ms"],
            ["Tokens", "512", "768", "+256"],
        ],
    )
    _draw_formula_box(
        page,
        fitz.Rect(54, 350, 558, 505),
        [
            r"$\mathcal{L}(\theta) = -\sum_i y_i \log p_i$",
            r"$F_1 = \frac{2PR}{P + R}$",
            r"$x_{t+1} = x_t - \alpha \nabla f(x_t)$",
        ],
    )
    _insert_paragraph(
        page,
        (
            "The final paragraph gives OCR workers a normal prose region after "
            "structured content, which is useful when checking reading order."
        ),
        fitz.Rect(54, 542, 558, 612),
    )

    document.save(output_path)
    document.close()


def generate_all(output_dir: Path = DEFAULT_OUTPUT_DIR) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        output_dir / "science_mixed_content.pdf",
        output_dir / "formula_table_fixture.pdf",
    ]
    create_science_mixed_pdf(outputs[0])
    create_formula_table_pdf(outputs[1])
    return outputs


if __name__ == "__main__":
    for generated_path in generate_all():
        print(generated_path)
