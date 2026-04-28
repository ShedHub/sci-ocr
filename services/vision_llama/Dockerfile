FROM python:3.13-slim

WORKDIR /app

COPY services/vision_llama/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared /app/shared
COPY services/vision_llama/app /app/services/vision_llama/app

ENV PYTHONPATH=/app

CMD ["uvicorn", "services.vision_llama.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
