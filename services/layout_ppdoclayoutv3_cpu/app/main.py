from fastapi import FastAPI
from fastapi import HTTPException

from shared.contracts.layout import LayoutReadyResponse, LayoutRequest, LayoutResponse

from .service import LayoutBackendUnavailable, get_ready, get_status, run_layout


app = FastAPI(title="layout_ppdoclayoutv3_cpu")


@app.get("/health")
def health() -> dict[str, str]:
    return get_status()


@app.get("/ready")
def ready() -> LayoutReadyResponse:
    try:
        return get_ready()
    except LayoutBackendUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/layout", response_model=LayoutResponse)
def layout(request: LayoutRequest) -> LayoutResponse:
    try:
        return run_layout(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LayoutBackendUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
