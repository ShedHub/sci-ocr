# Roadmap

## Done

- Define service-ready layout artifact contract
- Add local layout stub stage to the orchestrator pipeline
- Add `GET /ready` and `POST /layout` to `layout_stub`
- Add PDF page rendering to PNG at 300 or 400 DPI
- Update smoke test expectations for job and layout artifacts
- Make orchestrator call the HTTP `layout_stub` service instead of the local stub
- Add shared Docker volume configuration for job artifacts
- Add layout service failure persistence in `meta.json`, `trace.json`, and `logs.jsonl`
- Add an optional integration test for the real HTTP layout boundary
- Add shared Pydantic schemas for the layout service request/response contract
- Add deterministic block routing rules for OCR and future vision workers
- Expand crop generation beyond `title` and `text` blocks
- Add an OCR service contract and `ocr_stub` using the routing output
- Integrate block routing into the orchestrator pipeline
- Add orchestrator OCR stage for OCR-routed crops
- Add pending vision manifest for image/chart crops

## Next

- Stabilize CPU PP-DocLayoutV3 inference quality and label mapping
- Preserve native PP-DocLayoutV3 labels in normalized layout artifacts
- Replace `ocr_stub` with a GLM-OCR-compatible worker
- Add assembly stage for Markdown output
- Add a future vision service for image and chart blocks
- Add a separate GPU PP-DocLayoutV3 container and orchestrator backend switch
