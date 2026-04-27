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
- Add PP-DocLayoutV3 label mapping validation
- Preserve native PP-DocLayoutV3 labels in normalized layout artifacts
- Add representative PDF fixtures for text, tables, formulas, images, and charts
- Add a job validation report script for layout/OCR/vision split inspection
- Add deterministic orchestrator assembly stage for content stream and Markdown output
- Add a GLM-OCR worker behind the shared OCR contract
- Point Docker Compose OCR traffic at the GLM-OCR worker
- Verify a full Docker Compose run with PP-DocLayoutV3 and GLM-OCR on
  `formula_table_fixture.pdf`
- Add configurable layout and OCR HTTP timeouts for CPU model workers

## Next

- Validate CPU PP-DocLayoutV3 output quality on representative PDFs
- Validate GLM-OCR worker output quality on representative crops
- Improve OCR throughput with batching, parallel crop processing, or GPU
  execution
- Add a future vision service for image and chart blocks
- Improve assembly for multi-column reading order, paragraph merging, and
  figure/chart caption association
- Add a separate GPU PP-DocLayoutV3 container and orchestrator backend switch
