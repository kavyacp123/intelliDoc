"""
LLM Adapter — Hybrid Semantic SQL Generation via Groq.

Converts a natural language question into a validated DuckDB SQL query.

SECURITY CONTRACT:
  - ONLY schema metadata (column names + types) is sent to the LLM.
  - Dynamic semantics (inferred formulas) are also injected — still no raw data.
  - NEVER sends raw data values.
  - Output SQL is validated before execution (SELECT-only, AST-checked).

Flow:
  1. Receive normalized question + schema metadata + dynamic semantics
  2. Build a rich prompt with schema + semantic context
  3. Groq LLM returns raw SQL
  4. Strip markdown fences if present
  5. Return SQL for validation
"""

import re
from typing import Dict, List, Optional

from groq import Groq
from app.core.config import settings
from app.models.metadata import TableMetadata


import json

def generate_intent_json(
    question: str,
    schemas: List[TableMetadata],
    table_name: Optional[str] = None,
    semantics: Optional[Dict[str, str]] = None,
) -> dict:
    """
    Convert a natural language question into structured Intent JSON using Groq.
    """
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not configured in .env")

    # Build metric and dimension lists from schema
    all_columns = []
    time_columns = []
    for s in schemas:
        for c in s.columns:
            all_columns.append(c.name)
            if "date" in c.name.lower() or "time" in c.name.lower() or c.dtype.lower() in ["timestamp", "datetime", "date"]:
                time_columns.append(c.name)
                
    # Add inferred semantics (if any) to available metrics
    metrics = all_columns.copy()
    if semantics is not None:
        metrics.extend(semantics.keys())

    system_prompt = """You are a senior data query planner responsible for converting a user's natural language question into a structured multi-step execution plan.

Your job is NOT to generate SQL.

Your job is to:

1. Understand the user’s true intent
2. Decompose complex or ambiguous queries
3. Identify if multiple steps are required
4. Route each step into a structured intent compatible with the system

---

## INPUT CONTEXT

You are given:

* Database schema (columns, types)
* Derived metrics (if any)
* User query

You MUST NOT assume any column not present in schema.

---

## OUTPUT FORMAT (STRICT JSON)

Return a JSON object exactly matching this format:

{
"query_type": "simple | aggregation | ranking | detail | hybrid | exploratory",
"requires_multi_step": true/false,
"steps": [
{
"step_id": 1,
"intent_type": "aggregate | top_n | trend | comparison | row_level",
"description": "natural language description of this step",
"metric": "column or derived metric",
"dimensions": ["columns"],
"filters": {},
"order": "ASC | DESC | NONE",
"limit": 10,
"depends_on": null,
"output": "what this step produces (e.g., top_party)"
}
],
"final_output": {
"type": "table | summary | chart",
"description": "what user expects to see"
}
}

---

## IMPORTANT RULES

### 1. Detect MULTI-STEP queries
If query contains "and", "then", "also", "with details" or implicit dependency (e.g., "highest ... and details") -> MUST break into multiple steps.

### 2. Handle "DETAILS" correctly
If user asks for details/full data/show records, DO NOT treat "details" as a column.
Instead:
Create a SECOND step with:
  intent_type = "row_level"
  depends_on = previous step id
  filters = {"col_name": "previous_step_output"}

### 3. Ranking Logic
"top", "highest", "best" -> DESC
"lowest", "least" -> ASC
intent_type = "top_n"

### 4. NEVER hallucinate columns. Only use columns from the schema.
"""

    user_prompt = f"""Available Metrics:
{', '.join(metrics)}

Available Dimensions:
{', '.join(all_columns)}

Available Time Columns:
{', '.join(time_columns)}

User Question:
{question}
"""

    client = Groq(api_key=settings.GROQ_API_KEY)
    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0,
        response_format={"type": "json_object"}
    )

    json_str = response.choices[0].message.content.strip()
    
    # Strip markdown code fences if model adds them anyway
    json_str = re.sub(r"^```[a-zA-Z]*\n?", "", json_str)
    json_str = re.sub(r"\n?```$", "", json_str)
    json_str = json_str.strip()

    try:
        intent_dict = json.loads(json_str)
        return intent_dict
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM failed to generate valid JSON: {e}")



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
