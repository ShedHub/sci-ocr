# SCI-OCR

Stub-first document processing pipeline.

The project is being built around this flow:

```text
Input -> Page Rendering -> Layout -> OCR -> Assembly -> Output
```

## Current Capabilities

The system currently supports:

- FastAPI orchestrator
- `GET /health`
- `POST /run`
- input file validation
- unique job creation
- persistent job workspace on disk
- `meta.json`, `trace.json`, and `logs.jsonl`
- PDF page rendering to PNG at 300 DPI by default
- optional 400 DPI high-quality rendering through the `dpi` request field
- service-shaped layout stub artifacts for rendered pages
- layout stub service with `GET /health`, `GET /ready`, and `POST /layout`

OCR, PP-DocLayoutV3 inference, crop generation, and assembly are not
implemented yet.

## Project Structure

```text
sci-ocr/
+-- orchestrator/                 # API and pipeline logic
|   +-- app/
|       +-- main.py                 # FastAPI entrypoint
|       +-- pipeline.py             # Job creation and stage orchestration
|       +-- preparing_for_layout.py # PDF-to-PNG rendering stage
|       +-- layout_stage.py         # Local service-shaped layout stub stage
|       +-- schemas.py              # API request/response models
|       +-- config.py               # Path configuration
+-- jobs/
|   +-- input/                     # Optional input storage
|   +-- output/                    # Job results
+-- services/
|   +-- layout_stub/               # Layout HTTP stub
|   +-- ocr_stub/                  # OCR service placeholder
|   +-- assembly_stub/             # Assembly service placeholder
+-- docs/
+-- scripts/
+-- tests/
+-- docker-compose.yml
+-- README.md
```

## How To Run

Activate the local environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Start the orchestrator:

```powershell
uvicorn orchestrator.app.main:app --reload
```

Server:

```text
http://127.0.0.1:8000
```

## API

Health check:

```http
GET /health
```

Run a job:

```http
POST /run
```

Request body:

```json
{
  "input_path": "C:/input/test.pdf",
  "dpi": 300
}
```

`dpi` is optional and can be `300` or `400`. If omitted, the orchestrator uses
`300`.

Response:

```json
{
  "status": "accepted",
  "job_id": "job-20260421-213455-ab12cd",
  "input_path": "C:/input/test.pdf",
  "dpi": 300
}
```

## Job Output

Each request creates:

```text
jobs/output/<job_id>/
+-- original/
+-- preprocessed/
+-- assets/
|   +-- pages/
|   |   +-- page_0001.png
|   +-- layout/
+-- debug/
|   +-- preparing_for_layout.json
|   +-- layout_raw_page_0001.json
|   +-- layout_normalized_page_0001.json
+-- meta.json
+-- trace.json
+-- logs.jsonl
```

## What The System Does Now

```text
API request
-> validate input
-> create job_id
-> create job folder
-> copy input file
-> write initial metadata, trace, and log
-> render PDF pages to PNG at requested DPI
-> run local layout stub for rendered pages
-> write per-page raw and normalized layout artifacts
-> update meta.json, trace.json, and logs.jsonl
-> return job_id
```

## Current Limitations

- Layout uses a deterministic stub, not PP-DocLayoutV3.
- OCR is not implemented yet.
- Assembly is not implemented yet.
- The orchestrator does not call the HTTP layout service yet.
