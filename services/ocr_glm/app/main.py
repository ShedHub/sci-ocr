from fastapi import FastAPI, HTTPException

from shared.contracts.ocr import OcrReadyResponse, OcrRequest, OcrResponse

from .service import GlmOcrUnavailable, get_ready, get_status, run_ocr


app = FastAPI(title="ocr_glm")


@app.get("/health")
def health() -> dict[str, str]:
    return get_status()


@app.get("/ready")
def ready() -> OcrReadyResponse:
    try:
        return get_ready()
    except GlmOcrUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/ocr", response_model=OcrResponse)
def ocr(request: OcrRequest) -> OcrResponse:
    try:
        return run_ocr(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GlmOcrUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
