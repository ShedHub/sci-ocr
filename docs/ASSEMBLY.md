# Assembly

## Purpose

Assembly reconstructs the article as LLM-ready Markdown.

The input document may be a scanned scientific PDF. Earlier stages detect page
layout, crop each block, route text/table/formula blocks to OCR, and route
image/chart blocks to a future vision worker. Assembly turns those normalized
stage outputs into one ordered textual article.

Pipeline direction:

```text
PDF -> rendered pages -> layout -> crops -> OCR / vision -> content stream -> Markdown
```

The current assembly implementation is deterministic and lives inside the
orchestrator:

```text
orchestrator/app/assembly_stage.py
```

It is intentionally not a separate worker yet because it does not load a model
or perform heavy inference. It reads persisted artifacts and writes final job
outputs.

## Inputs

Assembly reads these job artifacts:

```text
debug/layout_normalized_page_XXXX.json
debug/ocr_normalized_page_XXXX.json
debug/layout_assets.json
debug/vision_pending_manifest.json
```

Layout provides the structural skeleton:

- page number
- block id
- block type
- native layout label when available
- bounding box
- layout order

OCR provides text content for OCR-routed blocks:

- text and headings as Markdown
- tables as Markdown
- formulas as LaTeX

Vision is not implemented yet. Until it exists, image and chart blocks enter
assembly as pending records from `vision_pending_manifest.json`.

## Content Stream

Assembly first writes a machine-readable stream:

```text
debug/content_stream.json
```

This is the canonical intermediate representation for the reconstructed
article. It is more important for debugging than the Markdown itself because it
shows the exact block order and source for every piece of content.

Each stream entry includes:

```json
{
  "page_number": 1,
  "order": 5,
  "block_id": "p1_b5",
  "block_type": "table",
  "layout_label": "table",
  "role": "table",
  "kind": "table",
  "bbox": [120, 300, 900, 620],
  "image_path": "jobs/output/.../assets/crops/page_0001/p1_b5.png",
  "target_service": "ocr",
  "status": "completed",
  "source": "ocr_stub",
  "format": "markdown",
  "content": "| A | B |\\n| --- | --- |"
}
```

Important fields:

- `role` describes how Markdown should treat the block, for example `heading`,
  `text`, `table`, `formula`, `caption`, `chart`, or `footer`.
- `kind` describes the content family, for example `text`, `table`, `formula`,
  `image`, or `chart`.
- `source` records where content came from, such as `ocr_stub`,
  `vision_pending`, or a future real OCR/vision worker.
- `status` is `completed`, `pending`, or `missing`.

## Ordering

The current ordering rule is:

```text
page_number -> order -> bbox top -> bbox left -> block_id
```

This handles the normal case and gives a stable fallback when the layout model
assigns the same `order` to multiple blocks. The rule is deterministic, which
makes regressions easy to test.

Known future improvements:

- better multi-column reading order
- paragraph merging across nearby text blocks
- caption association for figures and charts
- optional filtering of headers, footers, and page numbers

## Markdown Output

Assembly renders:

```text
output/article.md
```

Current rendering rules:

| Role / Kind | Markdown representation |
| --- | --- |
| `title` | `# Title` |
| `heading` | `## Heading` |
| `abstract` | `## Abstract` followed by text |
| text-like blocks | paragraph Markdown |
| `table` | Markdown table |
| display `formula` | fenced LaTeX block using `$$` |
| `inline_formula` | inline LaTeX using `$...$` |
| `caption` | italic Markdown |
| pending `chart` | blockquote placeholder |
| pending `image` | blockquote placeholder |

Example current output with stubs:

```markdown
## OCR stub text for p1_b1

OCR stub text for p1_b2

| source | block_id | role |
| --- | --- | --- |
| ocr_stub | p1_b5 | table |

$$
\mathrm{ocr\_stub}_{p1\_b7}
$$

> [Chart pending: p2_b3]

*OCR stub text for p2_b4*
```

With future real OCR and vision, the same position in the article should become:

```markdown
## Methods

The experiment measures response accuracy across three conditions.

| Condition | Accuracy |
| --- | ---: |
| A | 0.82 |
| B | 0.89 |

$$
\alpha = \frac{TP}{TP + FP}
$$

**Chart:** Accuracy rises from condition A to condition B.

Extracted chart data:

| Condition | Accuracy |
| --- | ---: |
| A | 0.82 |
| B | 0.89 |
```

## Manifest

Assembly writes:

```text
debug/assembly_manifest.json
```

The manifest summarizes:

- block count
- source counts
- role counts
- status counts
- warnings
- paths to `output/article.md` and `debug/content_stream.json`

Example:

```json
{
  "stage": "assembly",
  "status": "completed",
  "job_id": "job-0001",
  "blocks": 18,
  "sources": {
    "ocr_stub": 15,
    "vision_pending": 3
  },
  "statuses": {
    "completed": 15,
    "pending": 3
  }
}
```

## Validation

After running a job:

```powershell
.\.venv\Scripts\python.exe scripts\report_job.py <job_id>
```

Expected assembly section:

```text
Assembly:
  status: completed
  blocks: 18
  sources: ocr_stub=15, vision_pending=3
  statuses: completed=15, pending=3
  markdown: C:\project\jobs\output\<job_id>\output\article.md
  content stream: C:\project\jobs\output\<job_id>\debug\content_stream.json
```

For debugging, inspect `content_stream.json` first. If its order is correct but
Markdown is wrong, the bug is in rendering. If its order is wrong, the issue is
in layout order, bbox fallback, or future reading-order logic.
