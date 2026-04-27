FROM python:3.11-slim

WORKDIR /app

COPY services/layout_stub/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/layout_stub/app ./app
COPY shared ./shared

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
