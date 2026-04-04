"""
Insight Generation Engine (V5).

Converts raw analytical results into human-readable business insights using the Senior Data Analyst LLM.
"""

import json
import logging
from typing import Optional
from copy import deepcopy
from groq import Groq

from app.core.config import settings
from app.models.intent import MultiStepPlan
from app.schemas.query_schema import DashboardResponse

logger = logging.getLogger(__name__)

def generate_insights(data: list, question: str, sql: str, plan: Optional[MultiStepPlan] = None) -> DashboardResponse:
    """
    Derive business-level insights from result set using LLM.
    We limit the data sent to the LLM to 100 rows to save context window tokens.
    """
    if not data:
        return DashboardResponse(
            summary_card={"title": "No Data Found", "value": "0 raw rows", "description": "No significant trends found in the empty result set."}
        )

    # Limit payload to avoid blowing up Groq's context window
    truncated_data = data[:100]

    system_prompt = """You are a senior data analyst and dashboard generator.

Your task is to transform query results into a complete, structured dashboard response.

You must think like:
* A business analyst (extract meaning)
* A data scientist (identify patterns)
* A dashboard designer (decide what to display)

You do NOT generate SQL.

---

## OUTPUT FORMAT (STRICT JSON)

{
"summary_card": {
"title": "short headline insight",
"value": "key number or highlight",
"description": "1 sentence explanation"
},

"kpi_cards": [
{
"title": "KPI name",
"value": 123.45,
"description": "what it represents"
}
],

"chart": {
"type": "bar | line | pie | scatter | table",
"x_axis": "column name",
"y_axis": "column name",
"series": null,
"reason": "why this chart is best"
},

"insights_panel": [
{
"type": "trend | comparison | dominance | distribution",
"text": "clear business insight"
}
],

"anomalies": [
{
"text": "unexpected pattern",
"severity": "low | medium | high"
}
]
}

---

## RULES

### 1. Summary Card (MOST IMPORTANT)
* Must capture the **single most important takeaway**.
* Should feel like a dashboard headline.

### 2. KPI Cards
Always try to generate 2–5 KPIs such as:
* Total, Average, Maximum, Percentage contribution, Count
If data is categorical: include top contributor %

### 3. Chart Selection Logic
* Time column -> line chart
* Category vs value -> bar chart
* Share distribution -> pie chart
* Raw rows -> table

### 4. Insights Panel
Generate 2–4 insights: Who is leading, any imbalance, any pattern.

### 5. Anomalies Detection
Look for: Very low values, sudden spikes, outliers.

### 6. Be concise but meaningful
Avoid raw descriptions. Focus on decision-making insights.

## FINAL INSTRUCTION
Always prioritize clarity, business value, and dashboard usability.
Return ONLY valid JSON.
"""

    user_prompt = f"""
User Query: {question}
Executed SQL Context: {sql}

Result Data ({len(truncated_data)} sample rows out of {len(data)} total rows):
{json.dumps(truncated_data, default=str)}
"""

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=800,
            response_format={"type": "json_object"}
        )
        
        output_txt = response.choices[0].message.content
        result_json = json.loads(output_txt)
        return DashboardResponse(**result_json)
        
    except Exception as e:
        logger.error(f"Failed to generate insights via LLM: {e}")
        return DashboardResponse(
             summary_card={"title": "Analysis Error", "value": "N/A", "description": "Encountered an error generating dashboard insights due to LLM provider limits."}
        )
