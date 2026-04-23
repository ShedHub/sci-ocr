from fastapi import FastAPI

from .service import LayoutRequest, get_ready, get_status, run_layout


app = FastAPI(title="layout_stub")


@app.get("/health")
def health() -> dict[str, str]:
    return get_status()


@app.get("/ready")
def ready() -> dict[str, str]:
    return get_ready()


@app.post("/layout")
def layout(request: LayoutRequest) -> dict:
    return run_layout(request)
