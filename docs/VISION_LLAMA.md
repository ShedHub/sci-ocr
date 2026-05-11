# Vision Llama Backend

## Purpose

`vision_llama` is the current temporary vision backend for SCI-OCR.

It lets the pipeline process visual layout blocks before specialized image,
chart, and diagram extractors exist.

Pipeline position:

```text
PDF -> page rendering -> layout -> crops -> OCR + Vision -> assembly -> article.md
```

The layout stage may route image-like or chart-like blocks to `vision`.
`vision_llama` receives each visual crop, sends it to the containerized
multimodal `llama-server` service, normalizes the response, and assembly
inserts the Markdown into the final article. The adapter is the same for CPU
and GPU deployments; only the llama-server runtime changes.

## Local Files

The current local setup stores model files inside the project folder, but
outside Git. The `llama-server` binary itself is provided by llama.cpp container
images:

```text
CPU: ghcr.io/ggml-org/llama.cpp:server
GPU: ghcr.io/ggml-org/llama.cpp:server-cuda
```

```text
models/
  vision/
    qwen3.6-27b/
      Qwen3.6-27B-Q4_K_M.gguf
      mmproj-F16.gguf
```

These paths are intentionally ignored by `.gitignore`.

## Runtime Components

The vision runtime is container-only:

1. `llama_server_cpu`
   - Runs inside Docker through `docker-compose.yml`.
   - Uses the official `ghcr.io/ggml-org/llama.cpp:server` image.
   - Loads the mounted GGUF model and mmproj files from `models/vision/`.
   - Exposes an OpenAI-compatible endpoint at `http://llama_server:8080`
     inside the Compose network and at `http://127.0.0.1:8080` on the host.

2. `llama_server_gpu`
   - Runs inside Docker through `docker-compose.gpu.yml`.
   - Uses `ghcr.io/ggml-org/llama.cpp:server-cuda`.
   - Requests Nvidia GPU access with `gpus: all`.
   - Loads the same mounted GGUF model and mmproj files from `models/vision/`.
   - Uses the same `llama_server` Compose network alias as the CPU service.
   - Passes `--n-gpu-layers ${LLAMA_GPU_LAYERS:-999}` by default.

3. `vision_llama`
   - Runs as a Docker service.
   - Exposes `GET /health`, `GET /ready`, and `POST /vision`.
   - Calls the active llama-server runtime through `http://llama_server:8080`.

Start the Docker CPU runtime with:

```powershell
docker compose up -d llama_server_cpu layout_ppdoclayoutv3_cpu ocr_glm vision_llama orchestrator
```

Start the Docker GPU runtime with:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d \
  llama_server_gpu layout_ppdoclayoutv3_cpu ocr_glm_gpu vision_llama orchestrator
```

Check readiness:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
Invoke-RestMethod http://127.0.0.1:8006/ready
```

The CPU runtime can be tuned through `.env`:

```text
LLAMA_SERVER_PORT=8080
LLAMA_MODEL_PATH=/models/vision/qwen3.6-27b/Qwen3.6-27B-Q4_K_M.gguf
LLAMA_MMPROJ_PATH=/models/vision/qwen3.6-27b/mmproj-F16.gguf
LLAMA_CONTEXT_SIZE=4096
LLAMA_THREADS=16
```

The GPU runtime adds:

```text
LLAMA_SERVER_GPU_IMAGE=ghcr.io/ggml-org/llama.cpp:server-cuda
LLAMA_GPU_LAYERS=999
```

Lower `LLAMA_GPU_LAYERS` if the model does not fit in GPU memory.

## Start Docker Services

Build the affected CPU services:

```powershell
docker compose build layout_ppdoclayoutv3_cpu ocr_glm vision_llama orchestrator
```

Start the CPU pipeline services:

```powershell
docker compose up -d llama_server_cpu layout_ppdoclayoutv3_cpu ocr_glm vision_llama orchestrator
```

For Ubuntu + Nvidia GPU hosts, build and start through the GPU override:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml build ocr_glm_gpu orchestrator vision_llama
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d \
  llama_server_gpu layout_ppdoclayoutv3_cpu ocr_glm_gpu vision_llama orchestrator
```

Check readiness:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
Invoke-RestMethod http://127.0.0.1:8004/ready
Invoke-RestMethod http://127.0.0.1:8005/ready
Invoke-RestMethod http://127.0.0.1:8006/ready
Invoke-RestMethod http://127.0.0.1:8000/health
```

In GPU mode, OCR readiness is exposed on port `8007`:

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8007/ready
curl http://127.0.0.1:8006/ready
curl http://127.0.0.1:8000/health
```

## Run A Full Pipeline Test

Prepare a representative fixture:

```powershell
New-Item -ItemType Directory -Force jobs\input | Out-Null
Copy-Item tests\fixtures\pdfs\science_mixed_content.pdf jobs\input\science_mixed_content.pdf -Force
```

Run the orchestrator:

```powershell
$body = @{
  input_path = "/app/jobs/input/science_mixed_content.pdf"
  dpi = 300
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/run `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

Inspect the output:

```powershell
.\.venv\Scripts\python.exe scripts\report_job.py <job_id>
```

The validation report should show:

```text
vision: completed
pending blocks: 0
sources: GLM-OCR=..., qwen3.6-27b-q4_k_m=...
```

The assembled article is:

```text
jobs/output/<job_id>/output/article.md
```

## Prompt Behavior

`vision_llama` prompts in English.

The model is asked to classify the visual crop as one of:

```text
photo_or_illustration
chart_or_plot
diagram_or_flowchart
table_like_visual
unknown
```

Then it returns Markdown:

- illustrations get a concise scientific description;
- charts get axes, legend, trends, and approximate data tables when possible;
- diagrams or flowcharts get Mermaid when possible;
- unknown visuals get the best useful description plus uncertainty.

The prompt includes `/no_think` and asks for concise output. This is important
because the local Qwen model can spend a long time in reasoning mode if allowed
to generate freely.

## Artifacts

When vision completes, the job contains:

```text
debug/vision_manifest.json
debug/vision_raw_page_XXXX.json
debug/vision_normalized_page_XXXX.json
```

When vision is not configured, unavailable, or times out, the job contains:

```text
debug/vision_pending_manifest.json
```

Assembly reads normalized vision output first. If no completed vision output
exists for a visual block, assembly falls back to the pending manifest and emits
a placeholder in `article.md`.

## Known Limitations

This backend is deliberately temporary.

- It is slow on CPU-class local hardware. One visual crop can take several
  minutes. Use `llama_server_gpu` on Nvidia hosts to reduce latency.
- Chart data is approximate unless the values are printed clearly in the image.
- Layout labels can be wrong. For example, PP-DocLayoutV3 may label an
  illustration as `chart`. The prompt tells the model to classify from pixels,
  but routing metadata can still bias the result.
- Qwen may occasionally return empty final content after spending tokens in
  thinking/reasoning. The adapter now treats empty content as `degraded` and
  writes an explicit Markdown fallback instead of silently dropping the block.
- There is no structured JSON chart extractor yet. Markdown is the current
  normalized output for visual blocks.

## Tested Run

A full local run on `science_mixed_content.pdf` completed with:

```text
layout: completed, blocks=18, source=PP-DocLayoutV3
ocr: completed, blocks=15, source=GLM-OCR
vision: completed, blocks=3, source=qwen3.6-27b-q4_k_m
assembly: completed, blocks=18
pending blocks: 0
```

The bar chart was converted into Markdown with an extracted data table, and the
line chart was converted into a trend description.
