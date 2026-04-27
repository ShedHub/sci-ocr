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
- HTTP layout service calls for rendered pages
- layout stub service with `GET /health`, `GET /ready`, and `POST /layout`
- shared Pydantic schemas for the layout service request/response contract
- raw and normalized layout artifacts from the HTTP service boundary
- layout visual overlays in `assets/layout/page_XXXX_layout.png`
- `title` and `text` block crops in `assets/crops/page_XXXX/`

OCR and assembly are not implemented yet. A CPU PP-DocLayoutV3 service is
present, but its runtime behavior and label quality still need manual
end-to-end validation before it is treated as stable.

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
|   +-- layout_ppdoclayoutv3_cpu/  # CPU PP-DocLayoutV3 service
|   +-- ocr_stub/                  # OCR service placeholder
|   +-- assembly_stub/             # Assembly service placeholder
+-- shared/
|   +-- contracts/                 # Shared service boundary schemas
+-- models/                       # Local model folders; weights ignored by Git
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

Start the layout stub in a second terminal:

```powershell
uvicorn services.layout_stub.app.main:app --host 127.0.0.1 --port 8001
```

The orchestrator reads `LAYOUT_SERVICE_URL` from the environment. If omitted,
it uses `http://127.0.0.1:8001`. Docker Compose points it at
`layout_ppdoclayoutv3_cpu`; switch it back to `layout_stub` for stub-only runs.

Current real layout inference is CPU-only. A separate GPU layout container will
be added later, with orchestrator-level service selection through environment
configuration.

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
|   +-- crops/
|   |   +-- page_0001/
|   |       +-- p1_b1.png
|   +-- layout/
|       +-- page_0001_layout.png
+-- debug/
|   +-- preparing_for_layout.json
|   +-- layout_raw_page_0001.json
|   +-- layout_normalized_page_0001.json
|   +-- layout_assets.json
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
-> check HTTP layout service readiness
-> call HTTP layout service for each rendered page
-> write per-page raw and normalized layout artifacts
-> create layout overlays and title/text block crops
-> update meta.json, trace.json, and logs.jsonl
-> return job_id
```

## Current Limitations

- PP-DocLayoutV3 is wired as a CPU-only layout service, but still needs
  end-to-end runtime and quality validation.
- OCR is not implemented yet.
- Assembly is not implemented yet.
- A separate GPU layout container and orchestrator backend switch are planned
  for the future.
