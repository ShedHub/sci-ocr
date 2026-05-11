# Local Models

Model weights are stored locally and are not committed to Git.

Expected layout model path:

```text
models/layout/pp-doclayoutv3/
```

Expected OCR model path:

```text
models/ocr/glm-ocr/
```

Expected vision model path:

```text
models/vision/qwen3.6-27b/
+-- Qwen3.6-27B-Q4_K_M.gguf
+-- mmproj-F16.gguf
```

Docker Compose mounts `models/` into model-backed services as `/models`.

CPU and GPU service variants use the same local model directories:

- `layout_ppdoclayoutv3_cpu` reads `/models/layout/pp-doclayoutv3`.
- `ocr_glm` and `ocr_glm_gpu` read `/models/ocr/glm-ocr`.
- `llama_server_cpu` and `llama_server_gpu` read `/models/vision/qwen3.6-27b`.
