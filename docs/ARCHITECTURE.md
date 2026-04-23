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
- stub-first service boundaries

## Orchestrator

The orchestrator owns high-level pipeline flow:

- validate input files
- create job ids and job folders
- copy original inputs into `original/`
- write `meta.json`, `trace.json`, and `logs.jsonl`
- render PDF pages into `assets/pages/page_XXXX.png`
- call external services through stable contracts
- normalize service output for downstream stages

The orchestrator must not contain model-specific inference logic.

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
- routing blocks to OCR, table, formula, or figure pipelines

## Stub-First Path

Implementation order:

1. Keep the artifact contract stable.
2. Add a local service-shaped layout stub in the orchestrator pipeline.
3. Add a real HTTP `layout_stub` service with the same request/response shape.
4. Replace `layout_stub` with `PP-DocLayoutV3` behind the same contract.

The downstream pipeline must consume only normalized layout artifacts.
