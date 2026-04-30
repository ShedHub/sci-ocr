# Architecture

## Overview

SCI-OCR is a modular document processing pipeline.

```text
Input -> Page Rendering -> Layout -> OCR + Vision -> Assembly -> Output
```

The current implementation focuses on the foundation:

- FastAPI orchestrator
- persistent job workspace
- filesystem artifacts
- PDF-to-PNG page preparation for layout
- HTTP-backed stub-first service boundaries
- deterministic block routing rules for OCR and vision workers
- OCR HTTP boundary with contract-compatible stub and GLM-OCR workers
- optional vision HTTP boundary with a llama-server-backed adapter

## Orchestrator

The orchestrator owns high-level pipeline flow:

- validate input files
- create job ids and job folders
- copy original inputs into `original/`
- write `meta.json`, `trace.json`, and `logs.jsonl`
- render PDF pages into `assets/pages/page_XXXX.png`
- call the layout service through a stable HTTP contract
- normalize service output for downstream stages
- route layout blocks to the next worker service
- call the OCR service for OCR-routed crops
- call the optional vision service for image and chart crops
- write a pending vision manifest when the vision backend is unavailable
- assemble normalized artifacts into a content stream and Markdown output

The orchestrator must not contain model-specific inference logic.

## Block Routing

Block routing is the orchestration layer between layout and downstream workers.

Layout answers:

```text
what block exists, where it is, and what layout type it has
```

Routing answers:

```text
which service should process this block, which task it should run, and which
output format the pipeline expects
```

The routing rules live in `orchestrator/app/block_routing.py`.

Current routing direction:

```text
text-like blocks -> OCR service -> markdown
table blocks     -> OCR service -> markdown
formula blocks   -> OCR service -> latex
image/chart      -> optional vision service
```

The OCR stage consumes these routing decisions. It sends only OCR-routed crops
to the configured OCR worker. Image and chart crops are not sent to OCR; they
are handled by the optional vision stage or written to
`debug/vision_pending_manifest.json` when no vision backend is available.

Detailed routing rules are documented in `docs/BLOCK_ROUTING.md`.

## OCR Service

OCR is designed as an external persistent HTTP worker service.

Responsibilities:

- expose liveness through `GET /health`
- expose model readiness through `GET /ready`
- accept one cropped layout block through `POST /ocr`
- accept async cropped-block jobs through `POST /ocr/jobs`
- expose async job status and heartbeat through `GET /ocr/jobs/{task_id}`
- return recognized content in the format requested by the orchestrator

Docker Compose uses the `ocr_glm` worker, which loads the local GLM-OCR model
and implements the same shared contract. The `ocr_stub` worker remains available
for fast local tests; it validates the crop path and returns deterministic
placeholder content.

The GLM-OCR worker lives in `services/ocr_glm/`. Its container installs CPU
PyTorch wheels explicitly (`torch==2.9.1+cpu` and `torchvision==0.24.1+cpu`) so
the CPU deployment does not pull CUDA-sized dependencies. `torchvision` is
required by the GLM-OCR processor.

The worker maps the orchestrator's route decisions into GLM-OCR prompts:

```text
text    -> Text Recognition:
table   -> Table Recognition:
formula -> Formula Recognition:
```

The worker normalizes formula responses by removing outer Markdown display
wrappers such as `$$ ... $$` before returning LaTeX to the orchestrator.
Assembly owns the final Markdown wrapping.

Real CPU inference is slow compared with the stubs, so Docker Compose configures
async OCR job polling and larger service timeouts:

```text
LAYOUT_TIMEOUT_SECONDS=120
OCR_TIMEOUT_SECONDS=600
OCR_ASYNC_ENABLED=true
OCR_JOB_HTTP_TIMEOUT_SECONDS=30
OCR_JOB_POLL_INTERVAL_SECONDS=5
OCR_JOB_STALL_TIMEOUT_SECONDS=600
```

In async mode, the orchestrator does not hold a single long `POST /ocr` request
open while GLM-OCR runs. It starts a job, polls status, and only treats the job
as stalled when `last_heartbeat_at` stops updating beyond the configured stall
timeout. The current GLM-OCR implementation still calls `model.generate(...)`
as one blocking operation; a background heartbeat ticker marks the worker alive
during that call. Token-level progress is not implemented yet.

The request and response schemas live in `shared/contracts/ocr.py`. Both the
orchestrator and OCR service import this contract so the stub can be replaced by
a real OCR worker without changing the orchestrator boundary.

OCR request direction:

```json
{
  "job_id": "job-0001",
  "document_id": "paper.pdf",
  "page_number": 1,
  "block_id": "p1_b7",
  "block_type": "table",
  "layout_label": "table",
  "content_role": "table",
  "recognition_task": "table",
  "requested_format": "markdown",
  "image_path": "/app/jobs/output/job-0001/assets/crops/page_0001/p1_b7.png",
  "bbox": [120, 300, 900, 620],
  "order": 7
}
```

OCR response direction:

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
  "model": {
    "name": "GLM-OCR",
    "version": "local",
    "backend": "ocr_glm"
  },
  "warnings": [],
  "error": null,
  "service_time_ms": 1234
}
```

## Layout Service

Layout is designed as an external persistent HTTP service.

Responsibilities:

- load the layout backend once at service startup
- expose liveness through `GET /health`
- expose model readiness through `GET /ready`
- accept one rendered page through `POST /layout`
- return structured layout blocks with type, bbox, confidence, and order

The current real backend is `PP-DocLayoutV3`.

During development, `layout_stub` implements the same API shape without loading
the real model.

The request and response schemas live in `shared/contracts/layout.py`. Both the
orchestrator and layout service import this contract so backend replacement does
not change the HTTP boundary.

The PP-DocLayoutV3 service keeps backend-specific label mapping in its own
adapter module. Canonical layout block types leave the service boundary in
`type`, while the native model label is preserved in `layout_label` when
available.

The current PP-DocLayoutV3 runtime target is CPU-only and lives in
`services/layout_ppdoclayoutv3_cpu/`. A future GPU runtime should be added as a
separate service/container rather than changing the CPU service in place. The
orchestrator should keep selecting the active layout backend through
`LAYOUT_SERVICE_URL`.

CPU PP-DocLayoutV3 already uses Paddle/MKLDNN internal threading. Local
measurements show that one unrestricted worker is faster than several
underpowered workers limited to 2 CPU each. Future high-core deployments should
prefer a worker pool sized around roughly 10 CPU threads and 1.0-1.2 GB memory
per warmed layout worker, with pages distributed across workers for throughput.
The detailed notes and proposed auto-sizing strategy are documented in
`docs/LAYOUT_SCALING.md`.

## Persistent Container Rule

The layout container must not be started once per page.

Correct runtime model:

```text
docker compose up
  -> layout service starts
  -> PP-DocLayoutV3 loads once
  -> orchestrator sends page layout requests over HTTP
  -> service responds for each page or future batch
```

This avoids repeated model loading and keeps performance predictable.

## File Exchange

The preferred Docker integration is HTTP JSON plus shared volume paths.

Example request:

```json
{
  "job_id": "job-0001",
  "document_id": "test.pdf",
  "page_number": 1,
  "image_path": "/shared/jobs/output/job-0001/assets/pages/page_0001.png"
}
```

Both orchestrator and layout service should see the same mounted job workspace.
The layout service reads `image_path`; it does not receive large image bytes in
the normal path.

## Stage Ownership

Layout service owns:

- page layout detection
- block typing
- bbox and confidence output
- backend/model metadata

Orchestrator owns:

- page rendering from PDF to PNG
- raw artifact persistence
- normalized artifact persistence
- crop generation from bbox
- routing blocks to OCR or vision pipelines
- synchronous or async OCR request orchestration
- raw and normalized OCR artifact persistence
- vision request orchestration
- raw and normalized vision artifact persistence
- pending manifest persistence for unprocessed vision blocks

Routing module owns:

- mapping native layout labels to downstream service targets
- selecting the recognition task (`text`, `table`, `formula`, `image`, `chart`)
- selecting the requested output format (`markdown`, `latex`, or `none`)
- preserving content roles used later by Markdown assembly

OCR service owns:

- recognizing text-like block crops as Markdown
- recognizing table block crops as Markdown
- recognizing formula block crops as LaTeX
- reporting model metadata and service warnings

Vision service owns:

- processing image, figure, and chart block crops
- returning visual descriptions, chart extraction, Mermaid diagrams, or
  Markdown placeholders

Current temporary vision backend:

- `services/vision_llama` exposes `GET /health`, `GET /ready`, and
  `POST /vision`.
- It calls a separately running multimodal `llama-server` through its
  OpenAI-compatible chat completions endpoint.
- It prompts in English to classify visual blocks, describe illustrations,
  extract approximate chart data, and return Mermaid for diagrams when possible.
- If the backend is not configured or not ready, the orchestrator leaves visual
  blocks pending rather than failing the pipeline.

## Assembly Stage

Assembly is currently an orchestrator module, not a separate worker. It is
deterministic and model-free: it reads normalized layout artifacts, normalized
OCR artifacts, normalized vision artifacts, and pending vision artifacts, then
builds a linear article content stream.

The content stream is written to:

```text
debug/content_stream.json
```

The LLM-ready Markdown article is written to:

```text
output/article.md
```

Ordering is based on `page_number`, layout `order`, and bbox fallback
coordinates. This keeps headings, paragraphs, tables, formulas, captions, and
image/chart descriptions in the same approximate reading sequence as the source
article. If vision results are not available yet, assembly inserts
pending placeholders for image and chart blocks.

The detailed assembly contract is documented in `docs/ASSEMBLY.md`.

## Stub-First Path

Implementation order:

1. Keep the artifact contract stable.
2. Add a local service-shaped layout stub in the orchestrator pipeline.
3. Add a real HTTP `layout_stub` service with the same request/response shape.
4. Switch the orchestrator from the local stub to the HTTP `layout_stub`.
5. Replace `layout_stub` with `PP-DocLayoutV3` behind the same contract.

The downstream pipeline must consume only normalized layout artifacts.

OCR follows the same stub-first strategy:

1. Define the shared OCR contract.
2. Implement `ocr_stub` with `GET /health`, `GET /ready`, and `POST /ocr`.
3. Make the orchestrator call the OCR service for OCR-routed crops.
4. Persist raw and normalized OCR artifacts.
5. Replace Docker Compose OCR traffic with a GLM-OCR-compatible worker behind
   the same contract.

Vision follows the same replacement strategy:

1. Define the shared vision contract.
2. Implement a llama-server-backed adapter behind `POST /vision`.
3. Make the orchestrator call the vision service for routed visual crops.
4. Persist raw and normalized vision artifacts.
5. Later replace or augment the adapter with specialized image, chart, and
   diagram workers without changing assembly.
