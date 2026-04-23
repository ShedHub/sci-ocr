# schemas.py
"""
This file defines the shape of data your API accepts and returns.

It acts as a strict contract between:
client → API → pipeline

This ensures:
- input is validated before reaching pipeline logic
- responses are always consistent
"""

from typing import Literal

from pydantic import BaseModel


class RunRequest(BaseModel):
    # Absolute or relative path to input file
    input_path: str

    # PDF render quality for page images consumed by layout
    dpi: Literal[300, 400] = 300


class RunResponse(BaseModel):
    # "accepted" means job was successfully created
    status: str

    # Unique identifier for the job (used to locate results later)
    job_id: str

    # Echo of the input for traceability
    input_path: str

    # DPI used for PDF page rendering
    dpi: Literal[300, 400]
