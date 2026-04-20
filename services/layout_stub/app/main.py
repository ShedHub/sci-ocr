from fastapi import FastAPI


app = FastAPI(title="layout_stub")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "layout_stub"}
