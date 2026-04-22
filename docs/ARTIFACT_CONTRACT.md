# Artifact Contract

## Purpose

This document defines the artifact contract for the document processing pipeline.

Pipeline direction:

Input → Layout → OCR → Assembly → Output

At the current stage, implemented parts:

* job creation
* artifact system
* layout stage contract (stub-first)

The goal is to **keep stage boundaries stable**, so models can be replaced without breaking the system.

---

## Global Job Output Structure

Each request creates a job folder:

```
jobs/output/<job_id>/
├─ original/
├─ preprocessed/
├─ assets/
│  ├─ pages/
│  └─ layout/
├─ debug/
├─ meta.json
├─ trace.json
└─ logs.jsonl
```

---

## Folder Meaning

* `original/` — original input file (unchanged)
* `preprocessed/` — future normalized inputs (e.g., page images)
* `assets/pages/` — page images (future)
* `assets/layout/` — layout overlays / visualizations (future)
* `debug/` — machine-readable intermediate outputs
* `meta.json` — job summary and stage statuses
* `trace.json` — ordered timeline of pipeline events
* `logs.jsonl` — append-only structured logs

---

## Job-Level Files

### meta.json

Stores job state and stage statuses.

Example:

```json
{
  "job_id": "job-0001",
  "input_path": "C:/input/test.pdf",
  "status": "running",
  "stages": {
    "layout": {
      "status": "completed"
    }
  }
}
```

---

### trace.json

Stores ordered pipeline events.

Example:

```json
[
  {
    "event": "job_created",
    "timestamp": "2026-04-22T10:00:00Z"
  },
  {
    "event": "layout_started",
    "timestamp": "2026-04-22T10:00:01Z"
  },
  {
    "event": "layout_completed",
    "timestamp": "2026-04-22T10:00:02Z",
    "pages": 1,
    "blocks": 1
  }
]
```

---

### logs.jsonl

Append-only structured logs.

Example:

```json
{"timestamp":"2026-04-22T10:00:00Z","level":"INFO","event":"job_created"}
{"timestamp":"2026-04-22T10:00:01Z","level":"INFO","event":"layout_started"}
```

---

## Layout Stage Contract

### Purpose

The layout stage detects document structure and outputs:

1. raw layout (engine-specific)
2. normalized layout (project-standard)

---

## Layout Input

The layout stage receives:

* `input_path` — path to document
* `job_dir` — path to job output folder

Example:

```json
{
  "input_path": "C:/input/test.pdf",
  "job_dir": "C:/project/jobs/output/job-0001"
}
```

---

## Layout Output Files

The layout stage MUST create:

### 1. debug/layout_raw.json

Raw output of layout engine (or stub)

### 2. debug/layout_normalized.json

Canonical normalized layout used by pipeline

---

## Layout Status

Each layout stage ends with one of:

* `completed`
* `degraded`
* `failed`

These must be reflected in:

* meta.json
* trace.json
* logs.jsonl

---

## layout_raw.json (example)

```json
{
  "engine": "layout_stub",
  "pages": [
    {
      "page_number": 1,
      "detections": [
        {
          "label": "text",
          "bbox": [100, 100, 700, 180],
          "score": 0.98
        }
      ]
    }
  ]
}
```

⚠ Raw format is backend-specific
⚠ Do NOT use it downstream

---

## layout_normalized.json (canonical format)

```json
{
  "stage": "layout",
  "status": "completed",
  "source": "layout_stub",
  "pages": [
    {
      "page_number": 1,
      "blocks": [
        {
          "block_id": "p1_b1",
          "type": "text",
          "bbox": [100, 100, 700, 180],
          "confidence": 0.98,
          "order": 1,
          "source": "layout_stub"
        }
      ]
    }
  ]
}
```

---

## Normalized Layout Rules

### Top-level

* `stage` = "layout"
* `status` = completed | degraded | failed
* `source` = backend name
* `pages` = ordered list

---

### Page

Each page must contain:

* `page_number` (starts from 1)
* `blocks` (ordered list)

---

### Block

Each block must contain:

* `block_id` — unique (example: p1_b1)
* `type` — normalized type
* `bbox` — [x1, y1, x2, y2]
* `confidence` — float
* `order` — integer
* `source` — backend name

---

## Requirements

1. page_number starts from 1
2. block_id is unique
3. bbox has 4 numbers
4. order is integer
5. pages are ordered
6. blocks are deterministic
7. downstream uses ONLY normalized layout

---

## Supported Block Types (current)

Minimal set:

* text
* title
* table
* figure

---

## Failure Semantics

### completed

Valid output → continue pipeline

### degraded

Partial output → continue with caution

### failed

No valid output → stop or fallback

---

## Backend Replacement Rule

You must be able to replace:

layout_stub → PP-DocLayoutV3

WITHOUT changing:

* normalized format
* pipeline logic
* downstream stages

Only raw output may change.

---

## Current Phase Scope

This step guarantees:

* layout contract definition
* stub-compatible pipeline
* artifact structure

Not included yet:

* page rendering
* overlays
* reading order
* OCR
* assembly

---
