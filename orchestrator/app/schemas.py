'''
This file defines the shape of data your API accepts and returns.
What exactly is allowed to enter and leave the orchestrator?
'''
from pydantic import BaseModel


class RunRequest(BaseModel):
    input_path: str


class RunResponse(BaseModel):
    status: str
    job_id: str
    input_path: str
