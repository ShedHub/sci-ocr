# GPU Runtime

This project keeps CPU and GPU runtimes behind the same HTTP service
contracts. The orchestrator selects the active backend through service URLs;
the pipeline code does not change between CPU and GPU runs.

## Requirements

On the Ubuntu host:

```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

Both commands must show the Nvidia GPU. If the Docker command fails, install or
repair the Nvidia Container Toolkit before starting the GPU compose stack.

Docker Compose must support the `gpus` service field. The current project
configuration has been validated with Docker Compose v5.1.1. Recent Docker
Compose v2 releases should also work.

The local model folders must exist on the host because model weights are not
committed to Git:

```text
models/layout/pp-doclayoutv3/
models/ocr/glm-ocr/
models/vision/qwen3.6-27b/
  Qwen3.6-27B-Q4_K_M.gguf
  mmproj-F16.gguf
```

## GPU OCR

`ocr_glm_gpu` uses:

```text
services/ocr_glm/Dockerfile.gpu
```

It installs the CUDA PyTorch wheels for the same package versions used by the
CPU worker:

```text
torch==2.9.1
torchvision==0.24.1
CUDA wheel index: https://download.pytorch.org/whl/cu126
```

The CPU OCR service remains defined in `docker-compose.yml`, but the GPU
override changes the orchestrator dependency and URL so new jobs use
`ocr_glm_gpu`.

The GPU service sets:

```text
OCR_REQUIRE_CUDA=true
```

This makes readiness fail if the container cannot access CUDA, instead of
silently running the model on CPU.

## GPU Vision

`docker-compose.gpu.yml` also adds `llama_server_gpu` for visual blocks.
`vision_llama` is unchanged: it still calls `http://llama_server:8080` inside
the Compose network. In GPU mode that network alias points to the CUDA
`llama-server` service instead of the CPU one.

The GPU service uses the official llama.cpp CUDA server image:

```text
ghcr.io/ggml-org/llama.cpp:server-cuda
```

It passes:

```text
--n-gpu-layers ${LLAMA_GPU_LAYERS:-999}
```

Use a lower `LLAMA_GPU_LAYERS` value if the model does not fit in GPU memory.

## Start With GPU OCR And GPU Vision

Build and start the normal pipeline, but replace OCR and llama-server vision
runtime with GPU services:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml build \
  ocr_glm_gpu orchestrator vision_llama

docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d \
  llama_server_gpu layout_ppdoclayoutv3_cpu ocr_glm_gpu vision_llama orchestrator
```

Check readiness:

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8007/ready
curl http://127.0.0.1:8006/ready
curl http://127.0.0.1:8000/health
```

In this mode the orchestrator uses:

```text
OCR_SERVICE_URL=http://ocr_glm_gpu:8000
LLAMA_SERVER_URL=http://llama_server:8080
```

The CPU OCR worker remains available for CPU-only runs and local contract
testing.

## Smoke Test

Run the compact fixture:

```bash
mkdir -p jobs/input
cp tests/fixtures/pdfs/formula_table_fixture.pdf jobs/input/

curl -X POST http://127.0.0.1:8000/run \
  -H "Content-Type: application/json" \
  -d '{"input_path":"/app/jobs/input/formula_table_fixture.pdf","dpi":300}'
```

Inspect the job:

```bash
python scripts/report_job.py <job_id>
```

Expected high-level result:

```text
layout: completed
ocr: completed, source=GLM-OCR
assembly: completed
```

For a vision smoke test, run `science_mixed_content.pdf` and confirm the report
shows `vision: completed` with `pending blocks: 0`.

## Troubleshooting

- If `ocr_glm_gpu` readiness fails with a CUDA error, verify the host with
  `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi`.
- If `llama_server_gpu` exits because the model does not fit in VRAM, lower
  `LLAMA_GPU_LAYERS`.
- If port `8080` is already used, set `LLAMA_SERVER_PORT` in `.env`.
- If Docker Compose reports that `gpus` is unsupported, upgrade Docker Compose.
