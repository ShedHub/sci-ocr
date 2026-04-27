FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY services/layout_ppdoclayoutv3_cpu/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/layout_ppdoclayoutv3_cpu/app ./app
COPY shared ./shared

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
