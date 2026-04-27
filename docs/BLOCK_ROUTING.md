# Block Routing

## Purpose

Block routing is the decision layer between layout analysis and downstream
worker services.

The layout service answers:

```text
What block exists on the page, where is it, and what type is it?
```

The routing layer answers:

```text
Which worker service should process this block next?
Which recognition task should that worker run?
Which output format should the pipeline expect?
```

This keeps the orchestrator in control of the pipeline while keeping model
workers narrow and replaceable.

## Current Implementation

Routing rules live in:

```text
orchestrator/app/block_routing.py
```

The module is intentionally small and deterministic. It does not call external
services, read images, or perform model inference. It only maps layout block
labels to routing decisions.

The current route shape is:

```json
{
  "target_service": "ocr",
  "recognition_task": "text",
  "requested_format": "markdown",
  "content_role": "caption",
  "route_reason": "figure caption"
}
```

Field meaning:

- `target_service` says which downstream service owns the block.
- `recognition_task` says what kind of recognition the service should run.
- `requested_format` says which normalized output format is expected.
- `content_role` preserves the document semantics used by assembly.
- `route_reason` explains why the rule exists, for debugging and review.

## Target Services

Supported routing targets:

- `ocr`: text-oriented recognition service, expected to be backed by GLM-OCR.
- `vision`: future image, figure, and chart understanding service.
- `skip`: reserved for blocks that should not be processed downstream.

The current module only routes to `ocr` and `vision`.

## Recognition Tasks

Supported recognition tasks:

- `text`: text-like regions, titles, captions, headers, footers, references.
- `table`: table regions.
- `formula`: displayed or inline formula regions.
- `image`: image-like regions for a future vision service.
- `chart`: chart regions for a future chart/vision service.
- `none`: reserved for skipped blocks.

## Requested Formats

The project goal is PDF-to-Markdown conversion. Routing therefore requests
formats that are useful for final assembly:

- `markdown` for text and tables.
- `latex` for formulas.
- `none` for image/chart regions until the future vision service contract is
  defined.

This means the OCR worker should not decide the final representation by itself.
The orchestrator requests the representation needed by the pipeline.

## PP-DocLayoutV3 Labels

The local PP-DocLayoutV3 model declares these labels in:

```text
models/layout/pp-doclayoutv3/inference.yml
```

Supported native labels:

```text
abstract
algorithm
aside_text
chart
content
display_formula
doc_title
figure_title
footer
footer_image
footnote
formula_number
header
header_image
image
inline_formula
number
paragraph_title
reference
reference_content
seal
table
text
vertical_text
vision_footnote
```

The routing module can route these native labels directly. This is the preferred
future path because native labels preserve more detail than the current
canonical layout types. For example, `figure_title` and `text` are both
text-like, but they have different assembly roles.

## Native Label Routing Table

Text-like blocks routed to OCR as Markdown:

| Layout label | Target | Task | Format | Content role |
| --- | --- | --- | --- | --- |
| `abstract` | `ocr` | `text` | `markdown` | `abstract` |
| `algorithm` | `ocr` | `text` | `markdown` | `algorithm` |
| `aside_text` | `ocr` | `text` | `markdown` | `aside` |
| `content` | `ocr` | `text` | `markdown` | `paragraph` |
| `doc_title` | `ocr` | `text` | `markdown` | `title` |
| `figure_title` | `ocr` | `text` | `markdown` | `caption` |
| `footer` | `ocr` | `text` | `markdown` | `footer` |
| `footnote` | `ocr` | `text` | `markdown` | `footnote` |
| `header` | `ocr` | `text` | `markdown` | `header` |
| `number` | `ocr` | `text` | `markdown` | `page_number` |
| `paragraph_title` | `ocr` | `text` | `markdown` | `heading` |
| `reference` | `ocr` | `text` | `markdown` | `reference` |
| `reference_content` | `ocr` | `text` | `markdown` | `reference` |
| `seal` | `ocr` | `text` | `markdown` | `seal` |
| `text` | `ocr` | `text` | `markdown` | `text` |
| `vertical_text` | `ocr` | `text` | `markdown` | `vertical_text` |
| `vision_footnote` | `ocr` | `text` | `markdown` | `footnote` |

Table blocks routed to OCR as Markdown:

| Layout label | Target | Task | Format | Content role |
| --- | --- | --- | --- | --- |
| `table` | `ocr` | `table` | `markdown` | `table` |

Formula blocks routed to OCR as LaTeX:

| Layout label | Target | Task | Format | Content role |
| --- | --- | --- | --- | --- |
| `display_formula` | `ocr` | `formula` | `latex` | `formula` |
| `formula_number` | `ocr` | `formula` | `latex` | `formula_number` |
| `inline_formula` | `ocr` | `formula` | `latex` | `inline_formula` |

Image-like blocks routed to the future vision service:

| Layout label | Target | Task | Format | Content role |
| --- | --- | --- | --- | --- |
| `chart` | `vision` | `chart` | `none` | `chart` |
| `footer_image` | `vision` | `image` | `none` | `footer_image` |
| `header_image` | `vision` | `image` | `none` | `header_image` |
| `image` | `vision` | `image` | `none` | `image` |

## Canonical Type Fallback

The current normalized layout artifact only stores canonical block types:

```text
title
text
table
formula
figure
```

Until native labels are preserved in normalized layout blocks, the routing module
also supports fallback routing for these canonical types:

| Canonical type | Target | Task | Format | Content role |
| --- | --- | --- | --- | --- |
| `title` | `ocr` | `text` | `markdown` | `title` |
| `text` | `ocr` | `text` | `markdown` | `text` |
| `table` | `ocr` | `table` | `markdown` | `table` |
| `formula` | `ocr` | `formula` | `latex` | `formula` |
| `figure` | `vision` | `image` | `none` | `image` |

This fallback keeps the current pipeline compatible while we evolve the layout
contract to preserve native labels.

## Why Images And Charts Are Not Sent To OCR

Images, figures, and charts need a different downstream capability than OCR.
They may require captioning, chart data extraction, visual question answering,
or asset preservation.

For that reason:

```text
image/chart/header_image/footer_image -> vision service
```

The vision service is not implemented yet. Routing still marks these blocks so
future pipeline stages can keep them pending or emit placeholders in the final
Markdown.

## OCR Direction

The intended OCR worker is GLM-OCR or a compatible external service. The worker
should receive one cropped block image and the route decision from the
orchestrator.

Expected direction:

```json
{
  "job_id": "job-0001",
  "document_id": "paper.pdf",
  "page_number": 1,
  "block_id": "p1_b7",
  "layout_label": "table",
  "content_role": "table",
  "recognition_task": "table",
  "requested_format": "markdown",
  "image_path": "/app/jobs/output/job-0001/assets/crops/page_0001/p1_b7.png",
  "bbox": [120, 300, 900, 620],
  "order": 7
}
```

Expected response direction:

```json
{
  "status": "completed",
  "job_id": "job-0001",
  "page_number": 1,
  "block_id": "p1_b7",
  "content_role": "table",
  "recognition_task": "table",
  "format": "markdown",
  "content": "| A | B |\\n| --- | --- |\\n| 1 | 2 |",
  "confidence": null,
  "warnings": [],
  "error": null,
  "service_time_ms": 1234
}
```

This OCR contract is not implemented yet. The routing module is the foundation
that will feed it.

## Assembly Implications

Final assembly should not care which OCR model produced a block. It should
consume normalized block results ordered by page and layout order.

For Markdown output:

- text-like blocks are inserted as Markdown text;
- headings can be rendered as Markdown headings;
- tables are inserted as Markdown tables;
- formulas are inserted as LaTeX, either inline or display depending on
  `content_role`;
- images and charts can be inserted as placeholders until the vision service is
  implemented.

This is why routing preserves `content_role`: `text`, `caption`, `heading`,
`footer`, and `reference` may all use OCR task `text`, but assembly treats them
differently.

## Current Limitations

- The pipeline does not call the routing module yet.
- The OCR service contract is not implemented yet.
- The current layout service normalizes PP-DocLayoutV3 labels into a smaller
  canonical set, so downstream stages may lose native label detail until the
  normalized layout artifact is extended.
- Crop generation currently targets `title` and `text` blocks. A future routing
  stage should create or reuse crops for all blocks that are routed to OCR or
  vision.
