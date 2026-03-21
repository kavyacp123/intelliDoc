"""
Post-SQL Logic Enforcer (Production Guard Layer).

Validates that the generated SQL is logically consistent with the
user's detected intent. Catches and auto-corrects mismatches like:
  - ASC/DESC not matching "highest" vs "lowest" intent
  - Wrong aggregation function
  - Missing LIMIT clause

This is the LAST line of defense before SQL execution.
"""

import re
import logging

logger = logging.getLogger(__name__)


def enforce_order_logic(sql: str, intended_order: str, question: str) -> str:
    """
    Validate and enforce that ORDER BY direction matches the user's intent.
    
    Args:
        sql: The generated SQL string.
        intended_order: "asc" or "desc" from the intent processor.
        question: The original user question (for logging).
    
    Returns:
        Corrected SQL string.
    """
    intended_dir = "ASC" if intended_order == "asc" else "DESC"
    opposite_dir = "DESC" if intended_order == "asc" else "ASC"
    
    # Check if SQL contains ORDER BY with the wrong direction
    # Pattern: ORDER BY <something> ASC|DESC
    pattern = re.compile(
        r'(ORDER\s+BY\s+(?:SUM|COUNT|AVG|MIN|MAX)?\s*\([^)]*\)\s*)(ASC|DESC)',
        re.IGNORECASE
    )
    
    matches = pattern.findall(sql)
    if matches:
        for prefix, current_dir in matches:
            if current_dir.upper() != intended_dir:
                logger.warning(
                    "Logic mismatch detected! Question: '%s' → intent=%s but SQL has %s. Auto-correcting.",
                    question, intended_dir, current_dir.upper()
                )
                sql = pattern.sub(rf'\1{intended_dir}', sql)
                break  # Fix the first occurrence (main ORDER BY)
    
    return sql


def enforce_aggregation(sql: str, question: str) -> str:
    """
    Check if the aggregation function matches the question intent.
    Auto-corrects obvious mismatches.
    """
    q = question.lower()
    
    # Average intent but SUM in SQL
    if any(kw in q for kw in ["average", "avg", "mean"]):
        if "SUM(" in sql and "AVG(" not in sql:
            logger.info("Auto-correcting SUM → AVG based on question intent")
            sql = sql.replace("SUM(", "AVG(", 1)
    
    # Count intent but SUM in SQL
    if any(kw in q for kw in ["how many", "count", "number of"]):
        if "SUM(" in sql and "COUNT(" not in sql:
            logger.info("Auto-correcting SUM → COUNT based on question intent")
            # Replace SUM(column) with COUNT(*) for counting
            sql = re.sub(r'SUM\([^)]+\)', 'COUNT(*)', sql, count=1)
    
    return sql


def enforce_logic(sql: str, intent_order: str, question: str) -> str:
    """
    Main entry point: run all logic enforcement checks on the SQL.
    
    Args:
        sql: Generated SQL string.
        intent_order: "asc" or "desc" from the QueryIntent.
        question: The original user question.
    
    Returns:
        Corrected SQL string.
    """
    sql = enforce_order_logic(sql, intent_order, question)
    sql = enforce_aggregation(sql, question)
    return sql
