# main.py
"""
FastAPI entry point.

Responsibilities:
- receive HTTP request
- validate input (via Pydantic)
- call pipeline
- convert errors to HTTP responses
"""

from fastapi import FastAPI, HTTPException

from orchestrator.app.schemas import RunRequest, RunResponse
from orchestrator.app.pipeline import start_job

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run", response_model=RunResponse)
def run(request: RunRequest):
    try:
        job_id = start_job(request.input_path, dpi=request.dpi)

        return RunResponse(
            status="accepted",
            job_id=job_id,
            input_path=request.input_path,
            dpi=request.dpi,
        )

    except FileNotFoundError as e:
        # Input file does not exist
        raise HTTPException(status_code=404, detail=str(e))

    except ValueError as e:
        # Invalid input (e.g., folder instead of file)
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # Unexpected failure
        raise HTTPException(status_code=500, detail=str(e))
