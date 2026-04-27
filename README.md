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
- GLM-OCR worker service with `GET /health`, `GET /ready`, and `POST /ocr`
- HTTP OCR service calls for OCR-routed crops
- raw and normalized OCR artifacts from the HTTP service boundary
- pending vision manifest for image and chart blocks
- deterministic assembly stage that builds `content_stream.json` and
  `output/article.md` for LLM consumption
- representative test PDF fixture generation for text, tables, formulas,
  embedded images, bar charts, and line charts
- job validation reports through `scripts/report_job.py`

Docker Compose points OCR requests at the GLM-OCR worker by default. The
`ocr_stub` service remains available for fast local tests and contract
development. Assembly is implemented as a deterministic orchestrator module, so
its output is only as good as the upstream OCR and future vision/chart workers.
A CPU PP-DocLayoutV3 service is present and preserves native model labels, but
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
|       +-- assembly_stage.py       # Content stream and Markdown assembly
|       +-- schemas.py              # API request/response models
|       +-- config.py               # Path configuration
+-- jobs/
|   +-- input/                     # Optional input storage
|   +-- output/                    # Job results
+-- services/
|   +-- layout_stub/               # Layout HTTP stub
|   +-- layout_ppdoclayoutv3_cpu/  # CPU PP-DocLayoutV3 service
|   +-- ocr_stub/                  # OCR service placeholder
|   +-- ocr_glm/                   # GLM-OCR worker service
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
uses `http://127.0.0.1:8002`, which is convenient for local `ocr_stub` runs.
Docker Compose points it at `ocr_glm`. The GLM worker expects the local model
folder mounted at `/models/ocr/glm-ocr`.

Current real layout inference is CPU-only. A separate GPU layout container will
be added later, with orchestrator-level service selection through environment
configuration.

### Docker Compose With Real Layout And OCR

Docker Compose runs the real CPU layout service and the GLM-OCR worker by
default:

```powershell
docker compose build ocr_glm orchestrator
docker compose up -d layout_ppdoclayoutv3_cpu ocr_glm orchestrator
```

Check service readiness:

```powershell
Invoke-RestMethod http://127.0.0.1:8005/ready
Invoke-RestMethod http://127.0.0.1:8000/health
```

Run the compact fixture through the full pipeline:

```powershell
New-Item -ItemType Directory -Force jobs\input | Out-Null
Copy-Item tests\fixtures\pdfs\formula_table_fixture.pdf jobs\input\formula_table_fixture.pdf -Force

$body = @{
  input_path = "/app/jobs/input/formula_table_fixture.pdf"
  dpi = 300
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/run `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

Then inspect the job:

```powershell
.\.venv\Scripts\python.exe scripts\report_job.py <job_id>
```

The verified local smoke run produced `ocr: completed` with `source=GLM-OCR`
and assembled real text, table HTML, and LaTeX formulas into `output/article.md`.

The GLM-OCR image installs CPU PyTorch wheels explicitly:

```text
torch==2.9.1+cpu
torchvision==0.24.1+cpu
```

This avoids pulling CUDA-sized dependencies into the CPU container. The worker
also requires `torchvision` because the GLM-OCR processor depends on it.

Real CPU inference is much slower than the stubs. Docker Compose sets:

```text
LAYOUT_TIMEOUT_SECONDS=120
OCR_TIMEOUT_SECONDS=600
```

The compact one-page fixture currently takes several minutes on CPU because OCR
is called once per routed crop.

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
|   +-- content_stream.json
|   +-- assembly_manifest.json
+-- output/
|   +-- article.md
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
- assembly source/status summaries
- paths to rendered pages, overlays, crops, debug artifacts, and Markdown output

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
-> assemble article reading order into debug/content_stream.json
-> render output/article.md for downstream LLM analysis
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

## OCR Backends

The OCR boundary is implemented through `shared/contracts/ocr.py`.

The current `ocr_stub` exposes:

```text
GET /health
GET /ready
POST /ocr
```

It accepts one cropped block image at a time. Text and table requests ask for
Markdown output. Formula requests ask for LaTeX output. The stub validates the
crop path and returns deterministic placeholder content so tests can exercise
the full service boundary quickly.

Docker Compose uses `services/ocr_glm`, which implements the same contract with
the local GLM-OCR model. It maps route tasks to the model prompts:

```text
text    -> Text Recognition:
table   -> Table Recognition:
formula -> Formula Recognition:
```

## Assembly

The assembly stage lives in `orchestrator/app/assembly_stage.py`.

It reads normalized layout, normalized OCR, and pending vision artifacts, then
builds a linear `debug/content_stream.json` sorted by:

```text
page_number -> order -> bbox top -> bbox left -> block_id
```

The content stream is the machine-readable representation of the reconstructed
article. `output/article.md` is rendered from that stream for LLM analysis.
Text and tables are inserted as Markdown, formulas are inserted as LaTeX, and
image/chart blocks are represented as pending placeholders until a vision
service provides descriptions and chart data.

Detailed assembly design and validation notes are documented in
`docs/ASSEMBLY.md`.

## Current Limitations

- PP-DocLayoutV3 is wired as a CPU-only layout service and preserves native
  labels, but still needs quality validation on representative documents.
- GLM-OCR is wired as the Docker Compose OCR backend, while `ocr_stub` remains
  available for fast local contract tests.
- Real GLM-OCR CPU inference is slow because OCR-routed crops are processed
  sequentially; batching, parallelism, and/or GPU execution are future
  performance work.
- Assembly currently uses deterministic rules and placeholder OCR/vision
  content; it does not repair multi-column reading order or merge broken
  paragraphs beyond the order exposed by layout.
- The vision service for images and charts is not implemented yet; routed
  image/chart crops are written to `vision_pending_manifest.json`.
- A separate GPU layout container and orchestrator backend switch are planned
  for the future.
