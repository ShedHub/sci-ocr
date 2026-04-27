FROM python:3.11-slim

WORKDIR /app

COPY orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY orchestrator/app ./orchestrator/app
COPY shared ./shared

CMD ["uvicorn", "orchestrator.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
