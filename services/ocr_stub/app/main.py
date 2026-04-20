from fastapi import FastAPI


app = FastAPI(title="ocr_stub")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ocr_stub"}
