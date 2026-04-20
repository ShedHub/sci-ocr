from fastapi import FastAPI
from orchestrator.app.schemas import RunRequest, RunResponse
from orchestrator.app.pipeline import start_job

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run", response_model=RunResponse)
def run(request: RunRequest):
    job_id = start_job(request.input_path)

    return RunResponse(
        status="accepted",
        job_id=job_id,
        input_path=request.input_path,
    )
