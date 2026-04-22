# SCI-OCR

Stub-based document processing pipeline.

Current system provides:

* FastAPI orchestrator
* Job creation API
* Persistent job storage (filesystem-based)
* Metadata, trace, and logging for each job

---

## 📊 Current Capabilities

The system currently supports:

* Accepting document processing requests via API
* Validating input file paths
* Creating a unique job for each request
* Saving job artifacts to disk
* Returning a `job_id` for tracking

⚠️ No OCR, layout, or document parsing is implemented yet.

---

## 🧱 Project Structure

```
sci-ocr/
├── orchestrator/         # API + pipeline logic
│   └── app/
│       ├── main.py       # FastAPI entrypoint
│       ├── pipeline.py   # Job creation logic
│       ├── schemas.py    # API request/response models
│       ├── config.py     # Path configuration
│       ├── job_models.py # (empty, reserved)
│       └── job_storage.py# (empty, reserved)
├── jobs/
│   ├── input/            # Optional input storage
│   └── output/           # Job results (created automatically)
├── services/             # Stub services (not used yet)
├── docs/                 # Architecture and specs
├── scripts/              # Helper scripts
├── tests/                # Tests
├── docker-compose.yml
└── README.md
```

---

## 🚀 How to Run

### 1. Activate environment

Linux:

```
source .venv/bin/activate
```

Windows:

```
.\.venv\Scripts\Activate.ps1
```

---

### 2. Start API server

```
uvicorn orchestrator.app.main:app --reload
```

Server will run at:

```
http://127.0.0.1:8000
```

---

## 🌐 API Endpoints

### Health check

```
GET /health
```

Example:

```
curl http://127.0.0.1:8000/health
```

Response:

```
{"status": "ok"}
```

---

### Run job

```
POST /run
```

#### Request body

```
{
  "input_path": "/absolute/path/to/file.pdf"
}
```

---

### Example (Linux)

```
curl -X POST http://127.0.0.1:8000/run \
  -H "Content-Type: application/json" \
  -d '{"input_path": "/home/user/input/test.pdf"}'
```

---

### Example (Windows PowerShell)

```
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/run" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"input_path":"C:\\input\\test.pdf"}'
```

---

## 📥 Response

```
{
  "status": "accepted",
  "job_id": "job-20260421-213455-ab12cd",
  "input_path": "/path/to/file.pdf"
}
```

---

## 📂 Job Output Structure

Each request creates a folder:

```
jobs/output/<job_id>/
```

Example:

```
jobs/output/job-2026-.../
├── meta.json
├── trace.json
├── logs.jsonl
└── original/
    └── input_file.pdf
```

---

## 📄 File Descriptions

### meta.json

Main job summary:

* job_id
* status
* input paths
* timestamps

---

### trace.json

Timeline of events:

* job creation
* (future: pipeline stages)

---

### logs.jsonl

Append-only logs:

* one JSON per line
* structured logging format

---

### original/

Copy of the input file used for this job.

---

## ❌ Error Handling

### File does not exist

* HTTP 404

### Invalid path (not a file)

* HTTP 400

### Internal error

* HTTP 500

---

## 🧠 What the System Does Now

```
API request
→ validate input
→ create job_id
→ create job folder
→ copy input file
→ write metadata (meta.json)
→ write trace (trace.json)
→ write logs (logs.jsonl)
→ return job_id
```

---

## ⚠️ Limitations (Current State)

* No document parsing
* No OCR
* No layout detection
* No processing stages
* No service integration

The system only creates and manages job artifacts.

---

## 📌 Summary

This is a minimal orchestrator that:

* defines a stable API
* creates reproducible jobs
* stores all job data on disk

It is the foundation for a document processing pipeline.
