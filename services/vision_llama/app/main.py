from fastapi import FastAPI, HTTPException

from shared.contracts.vision import VisionReadyResponse, VisionRequest, VisionResponse

from .service import VisionLlamaUnavailable, get_ready, get_status, run_vision


app = FastAPI(title="vision_llama")


@app.get("/health")
def health() -> dict[str, str]:
    return get_status()


@app.get("/ready")
def ready() -> VisionReadyResponse:
    try:
        return get_ready()
    except VisionLlamaUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/vision", response_model=VisionResponse)
def vision(request: VisionRequest) -> VisionResponse:
    try:
        return run_vision(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VisionLlamaUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
