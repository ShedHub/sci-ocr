from fastapi import FastAPI


app = FastAPI(title="assembly_stub")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "assembly_stub"}
