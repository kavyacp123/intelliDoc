"""
Schema-Aware Query Router (Production Safety Layer).

Validates that every column referenced in generated SQL actually exists
in the target table. If any column is missing (e.g. the query planner
routed to a pre-aggregated table that lacks certain columns), the router
automatically falls back to the raw table and rewrites the SQL.

Flow:
  1. Parse SQL with sqlglot to extract referenced column names
  2. Query DuckDB DESCRIBE to get the target table's actual columns
  3. If all columns match → proceed with the planned table
  4. If mismatch → rewrite SQL to use the raw table instead
"""

import logging
from typing import Set

import sqlglot
from sqlglot import expressions as exp

from app.core.database import get_connection

logger = logging.getLogger(__name__)


def extract_columns_from_sql(sql: str) -> Set[str]:
    """
    Extract all column names referenced in a SQL string using sqlglot AST.

    Returns a set of lowercase column names found in SELECT, WHERE,
    GROUP BY, and ORDER BY clauses.
    """
    columns = set()
    try:
        parsed = sqlglot.parse_one(sql, dialect="duckdb")
        for col in parsed.find_all(exp.Column):
            columns.add(col.name.lower())
    except Exception as e:
        logger.warning("sqlglot column extraction failed: %s", e)
    return columns


def get_table_columns(table_name: str) -> Set[str]:
    """
    Get the actual column names of a DuckDB table via DESCRIBE.

    Returns a set of lowercase column names.
    """
    conn = get_connection()
    try:
        rows = conn.execute(f'DESCRIBE "{table_name}"').fetchall()
        return {row[0].lower() for row in rows}
    except Exception as e:
        logger.warning("Could not describe table '%s': %s", table_name, e)
        return set()


def rewrite_table_in_sql(sql: str, old_table: str, new_table: str) -> str:
    """
    Replace table references in SQL from old_table to new_table.

    Uses simple string replacement as a reliable fallback.
    """
    # Replace quoted and unquoted variants
    result = sql.replace(f'"{old_table}"', f'"{new_table}"')
    result = result.replace(f"'{old_table}'", f"'{new_table}'")
    result = result.replace(old_table, new_table)
    return result


def route_query(sql: str, plan: dict, raw_table: str) -> str:
    """
    Core routing logic: validate that the target table has all
    columns referenced by the SQL query. Falls back to raw table
    if any column is missing.

    Args:
        sql: The generated SQL string.
        plan: The execution plan dict from QueryPlanner (mutated in-place).
        raw_table: The base (raw/partitioned) table name for this dataset.

    Returns:
        The (possibly rewritten) SQL string.
    """
    target_table = plan.get("table", raw_table)

    # If already targeting the raw table, no routing needed
    if target_table == raw_table:
        return sql

    # Extract columns referenced in SQL
    sql_columns = extract_columns_from_sql(sql)
    if not sql_columns:
        return sql  # Couldn't parse — proceed as-is

    # Get actual columns of the target (agg) table
    target_columns = get_table_columns(target_table)
    if not target_columns:
        # Can't describe agg table — fall back to raw
        logger.warning("Table '%s' not found, falling back to raw '%s'", target_table, raw_table)
        return rewrite_table_in_sql(sql, target_table, raw_table)

    # Ignore system columns in the comparison
    system_columns = {"tenant_id", "total", "rank_n"}
    check_columns = sql_columns - system_columns

    # Check if all referenced columns exist in the target table
    if not check_columns.issubset(target_columns):
        missing = check_columns - target_columns
        logger.info(
            "Column mismatch on table '%s': missing %s. Falling back to raw '%s'",
            target_table, missing, raw_table
        )
        sql = rewrite_table_in_sql(sql, target_table, raw_table)
        plan["table"] = raw_table
        plan["used_pre_agg"] = False
        plan["fallback_reason"] = f"Missing columns: {missing}"
    else:
        logger.info("All columns validated for table '%s'", target_table)

    return sql
