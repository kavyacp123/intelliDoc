# 🔐 Secure AI Analytics Platform

A production-quality backend for secure, AI-powered data analytics with **zero data leakage**.

Natural language queries are converted to structured intent — **raw data is NEVER sent to an LLM**.

## Architecture

```
API Layer (FastAPI Routes)
        ↓
Service Layer (Business Logic)
        ↓
Core Engines:
    1. File Processing Engine     → Parse & load datasets
    2. Schema Engine              → Extract metadata (sent to LLM)
    3. Semantic Layer Engine      → Metrics & dimensions config
    4. LLM Adapter (Intent Only)  → NL → StructuredIntent
    5. Query Builder Engine       → Intent → SQL
    6. SQL Validator              → Safety checks
    7. Query Rewriter             → Tenant isolation
    8. Execution Engine           → DuckDB → JSON results
        ↓
Database Layer (DuckDB)
```

## Quick Start

### 1. Create virtual environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Edit `.env` with your settings (defaults work for local dev):

```
SECRET_KEY=your-secret-key-here
DATABASE_PATH=./data/analytics.duckdb
```

### 4. Start the server

```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Open API docs

Visit: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Usage

### Register a user

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@example.com", "password": "securepass123"}'
```

### Login

```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@example.com", "password": "securepass123"}'
```

### Upload a dataset

```bash
curl -X POST http://localhost:8000/upload \
  -H "Authorization: Bearer <your-token>" \
  -F "file=@example_data/sample_sales.csv"
```

### Query your data

```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "Show revenue by region"}'
```

---

## Security Principles

| Rule | Implementation |
|------|---------------|
| No raw data to LLM | Only schema metadata (column names + types) is sent |
| No LLM-generated SQL | LLM produces StructuredIntent → Query Builder creates SQL |
| Query validation | SELECT-only, whitelisted tables/columns, sqlglot AST parsing |
| Tenant isolation | `tenant_id` injected into every query via Query Rewriter |
| Rate limiting | Per-IP rate limiting middleware |
| Input sanitization | Pydantic validation on all inputs |

## Testing

```bash
python -m pytest tests/ -v
```

## Project Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI entry point
│   ├── core/
│   │   ├── config.py           # Settings (from .env)
│   │   ├── security.py         # JWT + bcrypt
│   │   └── database.py         # DuckDB connection
│   ├── models/                 # Domain models
│   ├── schemas/                # Pydantic request/response
│   ├── routes/
│   │   ├── auth_routes.py      # POST /register, /login
│   │   ├── dataset_routes.py   # POST /upload, GET /datasets
│   │   └── query_routes.py     # POST /query
│   ├── services/
│   │   ├── file_service.py     # File Processing Engine
│   │   ├── schema_service.py   # Schema Engine
│   │   ├── semantic_service.py # Semantic Layer Engine
│   │   ├── llm_service.py      # LLM Adapter (stub)
│   │   ├── query_builder_service.py
│   │   ├── validator_service.py
│   │   ├── rewrite_service.py
│   │   └── execution_service.py
│   └── utils/
├── tests/
├── semantic_config.yaml
├── example_data/
├── requirements.txt
└── .env
```
