from fastapi import FastAPI, HTTPException

from shared.contracts.ocr import OcrReadyResponse, OcrRequest, OcrResponse

from .service import get_ready, get_status, run_ocr


app = FastAPI(title="ocr_stub")


@app.get("/health")
def health() -> dict[str, str]:
    return get_status()


@app.get("/ready")
def ready() -> OcrReadyResponse:
    return get_ready()


@app.post("/ocr", response_model=OcrResponse)
def ocr(request: OcrRequest) -> OcrResponse:
    try:
        return run_ocr(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
