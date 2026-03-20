"""
LLM Adapter — Hybrid Semantic SQL Generation.

Converts a natural language question into a validated DuckDB SQL query.

SECURITY CONTRACT:
  - ONLY schema metadata (column names + types) is sent to the LLM.
  - Dynamic semantics (inferred formulas) are also injected — still no raw data.
  - NEVER sends raw data values.
  - Output SQL is validated before execution (SELECT-only, AST-checked).

Flow:
  1. Receive normalized question + schema metadata + dynamic semantics
  2. Build a rich prompt with schema + semantic context
  3. LLM returns raw SQL
  4. Strip markdown fences if present
  5. Return SQL for validation
"""

import re
from typing import Dict, List, Optional

from google import genai
from app.core.config import settings
from app.models.metadata import TableMetadata


def generate_sql(
    question: str,
    schemas: List[TableMetadata],
    table_name: Optional[str] = None,
    semantics: Optional[Dict[str, str]] = None,
) -> str:
    """
    Convert a natural language question directly into a DuckDB SQL query.

    Sends ONLY schema metadata (column names + types) and inferred semantic
    formulas to the LLM. Never sends raw data.

    Args:
        question: Natural language question (already synonym-normalized).
        schemas: List of table schemas (column names + types only).
        table_name: Optional target table name.
        semantics: Optional dict of inferred metrics { name: sql_expression }.

    Returns:
        A raw SQL string ready for validation and execution.
    """
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured in .env")

    # ── Build schema context string (metadata only — never raw data) ──
    schema_lines = []
    for s in schemas:
        cols = ", ".join(f"{c.name} ({c.dtype})" for c in s.columns)
        schema_lines.append(f"Table: {s.table_name}\nColumns: {cols}")
    schema = "\n\n".join(schema_lines)

    # ── Build semantic injection block (confidence gated) ──
    semantic_block = ""
    if semantics:
        lines = ["Inferred business metrics (use these derived formulas when they match the question):"]
        for name, expr in semantics.items():
            lines.append(f"  - {name} = {expr}")
        semantic_block = "\n".join(lines)

    # ── Assemble prompt ──
    prompt = f"""You are an expert data analyst and SQL generator.

Your task is to convert a natural language question into a valid DuckDB SQL query using ONLY the provided dataset schema.

=====================
DATASET SCHEMA:
{schema}
=====================
{f"""
=====================
INFERRED SEMANTIC METRICS:
{semantic_block}

Use these derived formulas when the user asks about profit, margins, etc.
If no relevant metric matches, fall back to the raw schema columns.
=====================
""" if semantic_block else ""}
STRICT RULES:
1. Use ONLY the columns listed in the schema above.
2. DO NOT invent or assume any column names.
3. DO NOT use any external knowledge.
4. Generate ONLY a SELECT query (no INSERT, UPDATE, DELETE, DROP).
5. Ensure the query is valid DuckDB SQL.
6. Use LIMIT 1000 unless specified otherwise.

QUERY LOGIC:
- Use SUM() for totals
- Use AVG() for averages
- Use COUNT(*) for counts
- Use GROUP BY when aggregating with categories
- Use ORDER BY when user asks for top/bottom results

DERIVED METRICS (ONLY IF POSSIBLE FROM AVAILABLE COLUMNS):
- If both "revenue" and "cogs" exist, you may compute profit = revenue - cogs
- If only a direct column exists, use it instead of deriving

HANDLING AMBIGUITY:
- If the question is ambiguous, choose the most reasonable interpretation based on column names
- If a requested concept does not exist, map it to the closest available column

OUTPUT FORMAT:
- Return ONLY the SQL query
- No explanation
- No comments
- No markdown

=====================
USER QUESTION:
{question}
=====================
"""

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )

    sql = response.text.strip()

    # Strip markdown code fences if model adds them anyway
    sql = re.sub(r"^```[a-zA-Z]*\n?", "", sql)
    sql = re.sub(r"\n?```$", "", sql)
    sql = sql.strip()

    return sql


def _infer_chart_hint(question: str) -> str:
    """Infer a chart type from the question wording."""
    q = question.lower()
    if any(w in q for w in ["trend", "over time", "timeline", "by month", "by year", "by quarter"]):
        return "line"
    if any(w in q for w in ["distribution", "breakdown", "share", "pie", "percent"]):
        return "pie"
    if any(w in q for w in ["by ", "per ", "group"]):
        return "bar"
    return "number"
