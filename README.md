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
- block crops for every layout block in `assets/crops/page_XXXX/`
- native PP-DocLayoutV3 labels preserved as `layout_label` when available
- block routing rules that map layout labels to OCR or future vision workers
- shared Pydantic schemas for the OCR service request/response contract
- OCR stub service with `GET /health`, `GET /ready`, and `POST /ocr`
- HTTP OCR service calls for OCR-routed crops
- raw and normalized OCR artifacts from the HTTP service boundary
- pending vision manifest for image and chart blocks
- representative test PDF fixture generation for text, tables, formulas,
  embedded images, bar charts, and line charts
- job validation reports through `scripts/report_job.py`

Real OCR and assembly are not implemented yet. The current OCR backend is a
stub that validates crop paths and returns deterministic placeholder content. A
CPU PP-DocLayoutV3 service is present and preserves native model labels, but
its output quality still needs manual end-to-end validation on representative
PDFs before it is treated as stable.

## Project Structure

```text
sci-ocr/
+-- orchestrator/                 # API and pipeline logic
|   +-- app/
|       +-- main.py                 # FastAPI entrypoint
|       +-- pipeline.py             # Job creation and stage orchestration
|       +-- preparing_for_layout.py # PDF-to-PNG rendering stage
|       +-- layout_stage.py         # Local service-shaped layout stub stage
|       +-- block_routing.py        # Layout block routing rules
|       +-- ocr_stage.py            # OCR HTTP stage and vision pending manifest
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
|       +-- layout.py
|       +-- ocr.py
+-- models/                       # Local model folders; weights ignored by Git
+-- docs/
+-- scripts/
+-- tests/
+-- docker-compose.yml
+-- README.md
```

## Test Fixtures

Representative PDFs can be regenerated with:

```powershell
.\.venv\Scripts\python.exe scripts\generate_test_pdfs.py
```

This writes:

```text
tests/fixtures/pdfs/formula_table_fixture.pdf
tests/fixtures/pdfs/science_mixed_content.pdf
```

`formula_table_fixture.pdf` is a compact one-page smoke document with prose,
a table, and rendered math formulas.

`science_mixed_content.pdf` is a two-page validation document with headings,
prose, a table, rendered formulas, an embedded image, a bar chart, and a
classic line graph. It is intended for validating PP-DocLayoutV3 labels, crop
generation, OCR routing, and future vision routing.

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

Start the OCR stub in a third terminal:

```powershell
uvicorn services.ocr_stub.app.main:app --host 127.0.0.1 --port 8002
```

The orchestrator reads `LAYOUT_SERVICE_URL` from the environment. If omitted,
it uses `http://127.0.0.1:8001`. Docker Compose points it at
`layout_ppdoclayoutv3_cpu`; switch it back to `layout_stub` for stub-only runs.

The orchestrator reads `OCR_SERVICE_URL` from the environment. If omitted, it
uses `http://127.0.0.1:8002`. Docker Compose points it at `ocr_stub`.

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
|   |       +-- p1_b2.png
|   +-- layout/
|       +-- page_0001_layout.png
+-- debug/
|   +-- preparing_for_layout.json
|   +-- layout_raw_page_0001.json
|   +-- layout_normalized_page_0001.json
|   +-- layout_assets.json
|   +-- ocr_manifest.json
|   +-- ocr_raw_page_0001.json
|   +-- ocr_normalized_page_0001.json
|   +-- vision_pending_manifest.json
+-- meta.json
+-- trace.json
+-- logs.jsonl
```

## Job Report

After running a job, print a compact validation report with:

```powershell
.\.venv\Scripts\python.exe scripts\report_job.py <job_id>
```

You may also pass a full job folder path:

```powershell
.\.venv\Scripts\python.exe scripts\report_job.py jobs\output\job-20260427-122837-9a453e
```

The report includes:

- stage statuses from `meta.json`
- per-page normalized layout blocks
- canonical type and native `layout_label` summaries
- crop routing split between OCR and future vision
- OCR task and output format summaries
- pending vision block summaries
- paths to rendered pages, overlays, crops, and debug artifacts

This is the preferred first check after running representative PDFs through
Docker Compose.

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
-> create layout overlays and crops for every layout block
-> route crops to OCR or future vision processing
-> check HTTP OCR service readiness
-> call HTTP OCR service for text/table/formula crops
-> write raw and normalized OCR artifacts
-> write pending vision manifest for image/chart crops
-> update meta.json, trace.json, and logs.jsonl
-> return job_id
```

## Block Routing

The routing layer lives in `orchestrator/app/block_routing.py`.

It maps layout blocks to the downstream worker that should process them next:

```text
text-like blocks -> OCR -> markdown
tables           -> OCR -> markdown
formulas         -> OCR -> latex
images/charts    -> future vision service
```

This module is deliberately deterministic and model-free. The OCR stage consumes
its decisions and sends only OCR-routed crops to the configured OCR worker.
Images and charts are recorded as pending for a separate future service.

Detailed routing rules are documented in `docs/BLOCK_ROUTING.md`.

## OCR Stub

The OCR boundary is implemented through `shared/contracts/ocr.py`.

The current `ocr_stub` exposes:

```text
GET /health
GET /ready
POST /ocr
```

It accepts one cropped block image at a time. Text and table requests ask for
Markdown output. Formula requests ask for LaTeX output. The stub does not run
real OCR; it validates the crop path and returns deterministic placeholder
content so the orchestrator can exercise the full service boundary.

## Current Limitations

- PP-DocLayoutV3 is wired as a CPU-only layout service and preserves native
  labels, but still needs quality validation on representative documents.
- Real OCR is not implemented yet; `ocr_stub` is a contract-compatible
  placeholder for a future GLM-OCR worker.
- Assembly is not implemented yet.
- The vision service for images and charts is not implemented yet; routed
  image/chart crops are written to `vision_pending_manifest.json`.
- A separate GPU layout container and orchestrator backend switch are planned
  for the future.
