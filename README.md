# 🔐 intelliDoc: Secure AI Analytics Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![DuckDB](https://img.shields.io/badge/DuckDB-FFF000?style=for-the-badge&logo=duckdb&logoColor=black)](https://duckdb.org/)
[![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-8E75B2?style=for-the-badge&logo=google%20gemini&logoColor=white)](https://aistudio.google.com/)

A production-quality backend for secure, AI-powered data analytics with **zero data leakage**.

Users can upload structured datasets and dynamically query them using natural language. The core value proposition of this application is that **raw data is NEVER sent to the LLM (Large Language Model)**. Instead, the backend uses AI solely to translate your natural language question into a secure, read-only SQL execution plan that processes entirely locally.

---

## 🏗️ Architecture & Component Flow

The platform relies on a multi-engine architecture built around FastAPI and DuckDB.

1. **API Layer (FastAPI)**: Users interact with secure, token-authenticated REST routes.
2. **File Processing Engine**: Ingests your dataset (CSV, Excel) and stores it natively in **DuckDB**, an embedded high-performance analytical database.
3. **Schema Engine**: Extracts exactly the *column headers and data types*. **This abstract schema is the ONLY thing transmitted to Google Gemini.**
4. **Semantic Layer (`semantic_config.yaml`)**: Maps business-friendly terms (e.g., "profit") into controlled SQL logic (e.g., `SUM(revenue - expense)`).
5. **LLM Adapter**: Prompts the LLM (Gemini) to return a structured JSON intent based purely on the schema and semantic configuration.
6. **Query Builder Engine**: Converts the structured JSON intent into valid DuckDB SQL syntax.
7. **SQL Validator & Query Rewriter**: Parses the Abstract Syntax Tree (AST) using libraries like `sqlglot`. It enforces that queries are `SELECT`-only, whitelists columns, and automatically injects a `tenant_id` to strictly isolate user data (**Tenant Isolation**).
8. **Execution Engine**: Executes the generated SQL against the local DuckDB instance and returns JSON formatted metrics to the user browser.

### Background Tier
- **Redis (`dump.rdb`)**: Serves as the high-speed data store for our custom 3-level application caching system, and serves as the message broker for Celery backend worker queues.
- **Worker/Celery Cluster**: Offloads heavy, long-running data analytics processes from the main FastAPI thread.

---

## 🚀 Getting Started

The application is contained inside the `backend/` directory. 

### 1. Configure the Environment
Inside `backend/`, copy or create a `.env` file according to the properties expected in `config.py`:
```env
# ── Security ──
SECRET_KEY=change-me-to-a-secure-random-string

# ── LLM Provider (stub | gemini) ──
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-actual-gemini-api-key

# ── Database ──
DATABASE_PATH=./data/analytics.duckdb
REDIS_URL=redis://localhost:6379/0
```
*(Note: If you do not have an API key, set `LLM_PROVIDER=stub` to test the pipeline using a fake, offline hardcoded engine).*

### 2. Stand up the API
Activate your virtual environment and run the Uvicorn webserver:
```bash
cd backend
python -m venv venv
venv\Scripts\activate   # On Windows
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload --port 8000
```

### 3. Open the Interactive Terminal
Navigate to [http://localhost:8000/docs](http://localhost:8000/docs) in your browser to access the automated Swagger UI Docs.

---

## 💻 API Lifecycle Overview

To successfully ask a question of your data, complete the requests in this exact order:

**1. Register & Login (`POST /register`, `POST /login`)**: 
   Since this platform is multi-tenant, you must uniquely identify your data. You will receive a JWT (Access Token). Authorize your Swagger UI using this token.

**2. Upload Data (`POST /upload`)**:
   Upload `example_data/sample_sales.csv`. 
   **Crucial:** Copy the `dataset_id` string from the JSON response!

**3. Ask Questions (`POST /query`)**:
   Provide your dataset ID and a natural language question in the JSON body:
   ```json
   {
      "question": "What is the total profit for clothing?",
      "dataset_id": "a1b2c3d4-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
   }
   ```

---

## 🔒 Security Principles Matrix
| Principle | Method of Implementation |
|-----------|------------------------|
| **Zero Code Execution** | No LLM-generated code/SQL runs arbitrarily. LLM only outputs JSON intentions.
| **Zero Data Leakage** | Only schema layouts are shipped to external APIs. Rows never leave the server.
| **Robust Validation** | Abstract Syntax Trees strictly lock operations down to basic `SELECT` math functions.
| **Hard Multi-Tenancy** | Request injection strictly partitions all `SELECT` queries globally by the authenticated User Token.
