# 🔐 intelliDoc: Secure AI Analytics Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![DuckDB](https://img.shields.io/badge/DuckDB-FFF000?style=for-the-badge&logo=duckdb&logoColor=black)](https://duckdb.org/)
[![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Groq](https://img.shields.io/badge/Groq-F55036?style=for-the-badge&logo=groq&logoColor=white)](https://groq.com/)
[![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)

A production-quality full-stack data intelligence platform for secure, AI-powered corporate analytics.

Users can upload structured datasets and dynamically query them using natural language. The core value proposition of this application is **Zero Data Leakage**. Raw data is **NEVER** sent to the LLM. Instead, the backend uses AI solely to translate your natural language question into a secure, read-only SQL execution plan that processes entirely locally on the server.

---

## 🏗️ Architecture & Component Flow

The platform utilizes a sophisticated multi-engine architecture split between a robust FastAPI backend and a streamlined, static HTML/Tailwind frontend.

1. **Frontend UI (Vanilla JS & Tailwind)**: A modern, glassmorphic analytics dashboard running directly in the browser via CDN. It handles JWT authentication, dataset management workflows, and interactive AI chat sessions natively.
2. **API Layer (FastAPI)**: Users interact through secure, OAuth2-authenticated REST API routes.
3. **Data Ingestion Engine**: Ingests your datasets (CSV, Excel) and automatically stores them in partitioned tables natively in **DuckDB**, an embedded high-performance analytical database. A unified virtual view is automatically built for downstream SQL.
4. **Dynamic Semantic Layer**: Inspects dataset structures upon upload to auto-generate derived business metrics (like `profit`, `margin`). It standardizes synonyms (e.g., "earnings" → "revenue") before queries hit the AI.
5. **LLM Adapter (Groq Llama 3)**: Prompts the Groq Cloud API with ONLY your structural schema and dynamic semantic definitions to rapidly generate deterministic DuckDB SQL.
6. **SQL Validator (sqlglot)**: Intercepts the generated SQL string before execution, parses the AST, guarantees `SELECT`-only operations, enforces strict column validation, and securely injects a `tenant_id` WHERE clause for **Hard Tenant Isolation**.
7. **Execution Engine**: Executes the validated SQL against the local DuckDB instance and pushes the JSON results back to the frontend to render data tables.

---

## 🚀 Getting Started

To run the full stack locally, you need two terminal windows: one for the backend, and one for the frontend.

### 1. Setup the Backend Environment
Inside the `backend/` directory, create a `.env` file according to `app/core/config.py`:
```env
# ── Security ──
SECRET_KEY=change-me-to-a-secure-random-string

# ── LLM Provider (stub | groq) ──
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_actual_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile

# ── Database ──
DATABASE_PATH=./data/analytics.duckdb
REDIS_URL=redis://localhost:6379/0
```
*(Note: Set `LLM_PROVIDER=stub` to test offline using a fake hardcoded engine without an API key).*

### 2. Stand up the API Server
Open Terminal 1:
```bash
cd backend
python -m venv venv
venv\Scripts\activate   # On Windows
pip install -r requirements.txt

# Start the FastApi server
uvicorn app.main:app --reload --port 8000
```
*(Optionally view raw API contracts at http://localhost:8000/docs)*

### 3. Launch the Frontend UI
Because the frontend uses pure HTML and CDN links for Tailwind, you just need a basic static web server.
Open Terminal 2:
```bash
cd frontend
python -m http.server 3000
```

### 4. Experience the Product
Navigate your web browser to **[http://localhost:3000/register_intellidoc/code.html](http://localhost:3000/register_intellidoc/code.html)**. Create a brand new account, log in, browse to the Dashboard, upload an Excel or CSV file on the left navigation bar, select it, and query it!

---

## 🔒 Security Principles Matrix

| Principle | Method of Implementation |
|-----------|------------------------|
| **Zero Data Leakage** | Rows never leave the server. Only column headers are pipelined to external AI APIs. |
| **Zero Code Execution** | No LLM runs unverified arbitrary logic. Output is treated as an untrusted string. |
| **Robust AST Validation** | Output syntax tree is parsed to lock operations down strictly to whitelisted `SELECT` math functions. |
| **Hard Multi-Tenancy** | Database tables inject `tenant_id` at ingestion, and the AST interceptor rigidly splices WHERE clauses filtering by Authenticated JWTs. |
