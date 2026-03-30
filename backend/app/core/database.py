"""
DuckDB database connection manager.

Provides a singleton connection and bootstraps the required system tables
(users, datasets) on first startup.  All tenant data tables are created
dynamically by the file_service when datasets are uploaded.
"""

import os
from pathlib import Path
from typing import Optional

import duckdb

from app.core.config import settings

# Module-level connection — acts as a singleton.
_connection: Optional[duckdb.DuckDBPyConnection] = None


def get_connection() -> duckdb.DuckDBPyConnection:
    """
    Return the singleton DuckDB connection.

    Creates the database file and parent directories if they don't exist.
    """
    global _connection
    if _connection is None:
        db_path = Path(settings.DATABASE_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _connection = duckdb.connect(str(db_path))
    return _connection


def init_db() -> None:
    """
    Bootstrap system tables.

    Called once at application startup (from main.py lifespan).
    """
    conn = get_connection()

    # Users table — stores auth credentials
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     VARCHAR PRIMARY KEY,
            email       VARCHAR UNIQUE NOT NULL,
            password    VARCHAR NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Dataset registry — tracks uploaded datasets per tenant
    conn.execute("""
        CREATE TABLE IF NOT EXISTS datasets (
            dataset_id  VARCHAR PRIMARY KEY,
            tenant_id   VARCHAR NOT NULL,
            table_name  VARCHAR NOT NULL,
            file_name   VARCHAR NOT NULL,
            row_count   INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Dataset metadata — stores column schemas
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dataset_metadata (
            dataset_id  VARCHAR NOT NULL,
            column_name VARCHAR NOT NULL,
            column_type VARCHAR NOT NULL,
            PRIMARY KEY (dataset_id, column_name)
        )
    """)
    
    # Migration: Add distinct_count if missing
    try:
        conn.execute("ALTER TABLE dataset_metadata ADD COLUMN distinct_count INTEGER DEFAULT 0")
    except Exception:
        # Column likely already exists
        pass

    # Chat history — stores conversational context per dataset
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id          VARCHAR PRIMARY KEY,    -- message id from frontend
            dataset_id  VARCHAR NOT NULL,
            tenant_id   VARCHAR NOT NULL,
            message     VARCHAR NOT NULL,       -- JSON serialized message object
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def close_db() -> None:
    """Close the database connection (called on shutdown)."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
