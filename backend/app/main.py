"""
FastAPI application entry point.

Sets up:
  - CORS middleware
  - Basic rate limiting middleware
  - Router registration (auth, datasets, query)
  - Database initialization on startup
  - Graceful shutdown
"""

import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import close_db, init_db
from app.services.rag_service import initialize_vector_store, seed_global_knowledge
from app.routes import (
    admin_routes,
    auth_routes, 
    dataset_routes, 
    query_routes, 
    google_auth_routes,
    history_routes,
    dashboard_routes
)
from starlette.middleware.sessions import SessionMiddleware

import os

# ── Logging ──
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

perf_logger = logging.getLogger("performance")
perf_logger.setLevel(logging.INFO)
perf_handler = logging.FileHandler("logs/performance.log")
perf_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
perf_logger.addHandler(perf_handler)


# ── Lifespan (startup / shutdown) ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB on startup, close on shutdown."""
    logger.info("🚀 Starting Secure AI Analytics Platform")
    init_db()
    logger.info("✅ Database initialized")
    seed_global_knowledge([
        {"term": "revenue", "resolution": "gross_total"},
        {"term": "sales", "resolution": "gross_total"},
        {"term": "profit", "resolution": "net_profit"},
        {"term": "quantity", "resolution": "quantity_sold"},
        {"term": "orders", "resolution": "order_count"},
        {"term": "customers", "resolution": "party_name"},
    ])
    try:
        initialize_vector_store()
    except Exception as e:
        logger.warning("Vector store initialization skipped: %s", e)
    yield
    close_db()
    logger.info("🛑 Database connection closed")


# ── FastAPI Application ──
app = FastAPI(
    title="Secure AI Analytics Platform",
    description=(
        "A production-quality backend for secure, AI-powered data analytics "
        "with zero data leakage. Natural language queries are converted to "
        "structured intent — raw data is NEVER sent to an LLM."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS Middleware ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite React dev server
        "http://localhost:5174",   # Vite fallback port
        "http://localhost:3000",   # Legacy frontend / alt port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Session Middleware (Required for Authlib OAuth2) ──
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)


# ── Basic Rate Limiting Middleware ──
# In production, use a proper solution like slowapi or Redis-backed limiter.
_request_counts: dict = defaultdict(list)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """
    Simple in-memory rate limiter.

    Tracks request timestamps per client IP and rejects requests
    that exceed the configured limit per minute.
    """
    if request.method == "OPTIONS":
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = 60  # seconds

    # Clean old entries
    _request_counts[client_ip] = [
        t for t in _request_counts[client_ip] if now - t < window
    ]

    if len(_request_counts[client_ip]) >= settings.RATE_LIMIT_PER_MINUTE:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded. Try again later."},
        )

    _request_counts[client_ip].append(now)
    response = await call_next(request)
    return response


# ── Register Routers ──
app.include_router(auth_routes.router)
app.include_router(google_auth_routes.router)
app.include_router(dataset_routes.router)
app.include_router(query_routes.router)
app.include_router(history_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(admin_routes.router)


# ── Health Check ──
@app.get("/health", tags=["System"])
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "Secure AI Analytics Platform"}
