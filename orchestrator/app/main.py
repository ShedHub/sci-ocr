from fastapi import FastAPI

app = FastAPI(title="SCI OCR Orchestrator")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/run")
async def run():
    return {
        "status": "ok",
        "message": "hello world",
        "service": "orchestrator",
    }
