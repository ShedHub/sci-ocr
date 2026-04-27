# Architecture

## Overview

SCI-OCR is a modular document processing pipeline.

```text
Input -> Page Rendering -> Layout -> OCR -> Assembly -> Output
```

The current implementation focuses on the foundation:

- FastAPI orchestrator
- persistent job workspace
- filesystem artifacts
- PDF-to-PNG page preparation for layout
- HTTP-backed stub-first service boundaries
- deterministic block routing rules for future OCR and vision workers

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
image/chart      -> future vision service
```

This keeps the orchestrator in charge of pipeline decisions while allowing the
OCR and vision services to stay narrow worker services. The intended OCR worker
is GLM-OCR or a compatible service, but the routing module does not depend on a
specific OCR implementation.

Detailed routing rules are documented in `docs/BLOCK_ROUTING.md`.

## Layout Service

Layout is designed as an external persistent HTTP service.

Responsibilities:

- load the layout backend once at service startup
- expose liveness through `GET /health`
- expose model readiness through `GET /ready`
- accept one rendered page through `POST /layout`
- return structured layout blocks with type, bbox, confidence, and order

The planned real backend is `PP-DocLayoutV3`.

During development, `layout_stub` implements the same API shape without loading
the real model.

The request and response schemas live in `shared/contracts/layout.py`. Both the
orchestrator and layout service import this contract so backend replacement does
not change the HTTP boundary.

The PP-DocLayoutV3 service keeps backend-specific label mapping in its own
adapter module. Only canonical layout block types leave the service boundary.

The current PP-DocLayoutV3 runtime target is CPU-only and lives in
`services/layout_ppdoclayoutv3_cpu/`. A future GPU runtime should be added as a
separate service/container rather than changing the CPU service in place. The
orchestrator should keep selecting the active layout backend through
`LAYOUT_SERVICE_URL`.

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
- routing blocks to OCR or future vision pipelines

Routing module owns:

- mapping native layout labels to downstream service targets
- selecting the recognition task (`text`, `table`, `formula`, `image`, `chart`)
- selecting the requested output format (`markdown`, `latex`, or `none`)
- preserving content roles used later by Markdown assembly

OCR service owns, once implemented:

- recognizing text-like block crops
- recognizing table block crops as Markdown
- recognizing formula block crops as LaTeX

Future vision service owns:

- processing image, figure, and chart block crops
- returning visual descriptions, chart extraction, or Markdown placeholders

## Stub-First Path

Implementation order:

1. Keep the artifact contract stable.
2. Add a local service-shaped layout stub in the orchestrator pipeline.
3. Add a real HTTP `layout_stub` service with the same request/response shape.
4. Switch the orchestrator from the local stub to the HTTP `layout_stub`.
5. Replace `layout_stub` with `PP-DocLayoutV3` behind the same contract.

The downstream pipeline must consume only normalized layout artifacts.
