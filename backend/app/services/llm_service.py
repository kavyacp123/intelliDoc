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

    system_prompt = """You are an analytics intent parser.

Your job is to convert a user query into structured JSON.

Rules:
* DO NOT generate SQL
* ONLY return valid JSON
* Use ONLY available metrics and dimensions
* CRITICAL SEMANTIC MAPPING: You must map broad business terms in the user's query to the precise available column that best matches. 
  - e.g. If they ask for "customer" or "client", map it to "buyer", "client_name", etc.
  - e.g. If they ask for "value", "sales", or "revenue", map it to "gross_total", "amount", "net_sales", etc.
* Detect:
  * operation (aggregate, top_n, trend, comparison)
  * metric (a single column name to aggregate)
  * dimensions (list of column names to select)
  * group_by (list of column names to group by)
  * time_grain (year, month, day)
  * filters (list of filter objects)
  * order ("asc" or "desc")
* NEVER output SQL

Intent Operation Rules:
* "best", "top", "highest" -> operation = top_n, order = "desc"
* "worst", "bottom", "lowest", "least" -> operation = top_n, order = "asc"
* "trend", "over time" -> operation = trend
* "compare", "vs" -> operation = comparison

ORDER RULES (CRITICAL):
* "highest", "most", "top", "best", "maximum" -> order = "desc"
* "lowest", "least", "bottom", "worst", "minimum" -> order = "asc"
* Default: order = "desc"

CRITICAL FILTER FORMAT:
* filters MUST ALWAYS be a LIST of objects
* Each filter object MUST have exactly: "column", "operator", "value"
* NEVER return filters as a flat dictionary

CORRECT filters format:
  "filters": [{"column": "product", "operator": "=", "value": "Paseo"}]

WRONG filters format (NEVER do this):
  "filters": {"product": "Paseo"}
"""

    user_prompt = f"""Available Metrics:
{', '.join(metrics)}

Available Dimensions:
{', '.join(all_columns)}

Available Time Columns:
{', '.join(time_columns)}

User Question:
{question}

EXAMPLES:
Input: "how many units of Paseo were sold in Mexico"
Output:
{{
  "metric": "quantity",
  "dimensions": [],
  "operation": "aggregate",
  "group_by": [],
  "order": "desc",
  "filters": [{{"column": "product", "operator": "=", "value": "Paseo"}}, {{"column": "country", "operator": "=", "value": "Mexico"}}]
}}

Input: "best product per year"
Output:
{{
  "metric": "revenue",
  "dimensions": ["product"],
  "operation": "top_n",
  "group_by": ["year"],
  "rank": 1,
  "order": "desc",
  "time_grain": "year",
  "filters": []
}}

Input: "lowest revenue category by region"
Output:
{{
  "metric": "revenue",
  "dimensions": ["category"],
  "operation": "top_n",
  "group_by": ["region"],
  "rank": 1,
  "order": "asc",
  "filters": []
}}
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
