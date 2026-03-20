"""
Execution Engine (Service 8 of 8).

Executes validated and rewritten SQL queries against DuckDB
and returns results as JSON-serializable dictionaries.

Safety guarantees at this point:
  - Query has been validated (SELECT-only, whitelisted tables/columns)
  - Query has been rewritten (tenant_id injected, LIMIT enforced)
  - This engine only needs to execute and return results safely
"""

import concurrent.futures
import logging
from typing import Any, Dict, List

from app.core.config import settings
from app.core.database import get_connection

logger = logging.getLogger(__name__)


class QueryExecutionError(Exception):
    """Raised when SQL execution fails."""

    pass


def execute_query(sql: str) -> List[Dict[str, Any]]:
    """
    Execute a SQL query and return results as a list of dicts.

    The query MUST have already passed through:
      1. validator_service.validate_query()
      2. rewrite_service.rewrite_query()

    Args:
        sql: The validated, rewritten SQL query.

    Returns:
        List of row dicts, e.g. [{"region": "East", "revenue": 5000}, ...]

    Raises:
        QueryExecutionError: If execution fails for any reason.
    """
    conn = get_connection()

    try:
        logger.info("Executing query: %s", sql)

        def _run():
            cursor = conn.cursor()
            result = cursor.execute(sql)
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()
            cursor.close()
            
            data = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    row_dict[col] = _make_serializable(row[i])
                data.append(row_dict)
            return data

        # Enforce 2-second timeout
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run)
            try:
                data = future.result(timeout=2.0)
            except concurrent.futures.TimeoutError:
                raise QueryExecutionError("Query execution timed out after 2 seconds")

        logger.info("Query returned %d rows", len(data))
        return data

    except Exception as e:
        logger.error("Query execution failed: %s | SQL: %s", str(e), sql)
        raise QueryExecutionError(f"Query execution failed: {str(e)}")


def _make_serializable(value: Any) -> Any:
    """
    Convert a value to a JSON-serializable type.

    Handles DuckDB-specific types like dates, timestamps, Decimals, etc.
    """
    if value is None:
        return None
    if isinstance(value, (int, float, str, bool)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    # Datetime, date, Decimal, etc.
    return str(value)
