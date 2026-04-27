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

## Next

- Stabilize CPU PP-DocLayoutV3 inference quality and label mapping
- Add OCR and assembly stages
- Add a separate GPU PP-DocLayoutV3 container and orchestrator backend switch
