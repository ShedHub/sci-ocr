from fastapi import FastAPI
from fastapi import HTTPException

from shared.contracts.layout import LayoutReadyResponse, LayoutRequest, LayoutResponse

from .service import get_ready, get_status, run_layout


app = FastAPI(title="layout_stub")


@app.get("/health")
def health() -> dict[str, str]:
    return get_status()


@app.get("/ready")
def ready() -> LayoutReadyResponse:
    return get_ready()


@app.post("/layout", response_model=LayoutResponse)
def layout(request: LayoutRequest) -> LayoutResponse:
    try:
        return run_layout(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
