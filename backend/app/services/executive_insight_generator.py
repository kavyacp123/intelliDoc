"""
Executive Dashboard Insight Generator.

Takes the fully hydrated dashboard data (KPIs, sections, predefined query results)
and generates professional, CFO-level financial insights via the Groq LLM.

Triggered only when the user clicks "Generate AI Insights" — never runs automatically.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from groq import Groq
from app.core.config import settings

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """You are a senior financial analyst and business intelligence expert reporting directly to a CFO.

Your task is to generate professional, data-driven insights based ONLY on the provided dashboard data.

STRICT RULES:
- ONLY use the provided data. DO NOT assume or hallucinate missing values.
- DO NOT invent trends not visible in data.
- If data is insufficient → explicitly say so.
- Be precise, factual, and decision-oriented.
- Use quantitative language (use numbers where possible).

---

## ANALYSIS STEPS

### STEP 1: KPI INSIGHTS
- Profit margin → strong (>20%) / moderate (10-20%) / weak (<10%)
- Revenue vs Cost relationship
- Any anomalies in KPI figures

### STEP 2: PERFORMANCE INSIGHTS
From grouped data:
- Identify top-performing entities (by highest revenue/profit)
- Identify underperforming entities
- Highlight concentration (e.g., "top 20% contributes 80%" if visible)

### STEP 3: TREND INSIGHTS (only if time data exists)
- Is revenue increasing, decreasing, or stable?
- Is profit improving or declining?
- Any unusual spikes or drops?

### STEP 4: COST INSIGHTS
- Is cost proportion high relative to revenue?
- Which segments are cost-heavy?

### STEP 5: RISK & OPPORTUNITY
- Highlight risks (low margin, high cost)
- Highlight opportunities (high-performing segments)

---

## OUTPUT FORMAT (STRICT JSON)

{
  "summary": "One-paragraph executive summary (2-3 sentences max)",
  "insights": [
    {
      "type": "profitability | performance | trend | cost | risk",
      "title": "Short headline",
      "description": "Detailed insight with numbers",
      "confidence": "high | medium | low"
    }
  ],
  "recommendations": [
    {
      "action": "Specific actionable recommendation",
      "reason": "Data-backed justification"
    }
  ]
}

---

## WRITING STYLE
- Professional (like a CFO report)
- Concise (no long paragraphs)
- Quantitative (use numbers where possible)
- Avoid vague language like "doing well" or "looks okay"

## GOOD EXAMPLES
✔ "Profit margin is 14.2%, indicating moderate profitability with room for optimization."
✔ "Product X contributes approximately 45% of total revenue, showing strong market concentration."
✔ "Product Y underperforms with ₹2.1K revenue vs peer average of ₹12.5K."

## BAD EXAMPLES
✘ "Business is doing well"
✘ "Looks like revenue is okay"
✘ Any guess without data

Return ONLY valid JSON. No markdown fences. No explanations outside JSON."""


def _prepare_dashboard_context(dashboard_data: Dict[str, Any]) -> str:
    """
    Prepare a concise context string from dashboard data for the LLM.
    Limits data to avoid blowing up context window.
    """
    context_parts = []

    # KPIs
    kpis = dashboard_data.get("kpis", [])
    if kpis:
        kpi_summary = []
        for kpi in kpis:
            kpi_summary.append(f"- {kpi['name']}: {kpi['value']} (raw: {kpi.get('raw_value', 'N/A')})")
        context_parts.append("KPI METRICS:\n" + "\n".join(kpi_summary))

    # Sections (chart data)
    sections = dashboard_data.get("sections", [])
    if sections:
        section_summaries = []
        for section in sections:
            title = section["title"]
            data = section.get("data", [])
            # Limit to top 10 rows per section
            truncated = data[:10]
            section_summaries.append(f"\n--- {title} ({section['chart_type']} chart) ---\n{json.dumps(truncated, default=str)}")
        context_parts.append("SECTION DATA:" + "\n".join(section_summaries))

    # Detected fields
    fields = dashboard_data.get("detected_fields", {})
    if fields:
        context_parts.append(f"DETECTED SCHEMA FIELDS:\n"
                             f"  Revenue column: {fields.get('revenue', 'Not found')}\n"
                             f"  Cost column: {fields.get('cost', 'Not found')}\n"
                             f"  Time column: {fields.get('time', 'Not found')}\n"
                             f"  Dimensions: {', '.join(fields.get('dimensions', []))}")

    # Notes
    notes = dashboard_data.get("notes", [])
    if notes:
        context_parts.append("NOTES:\n" + "\n".join(f"- {n}" for n in notes))

    return "\n\n".join(context_parts)


def generate_executive_insights(dashboard_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate professional financial insights from executive dashboard data.

    Args:
        dashboard_data: The full dashboard JSON (kpis, sections, predefined_queries, etc.)

    Returns:
        Dict with summary, insights array, and recommendations array.
    """
    if not settings.GROQ_API_KEY:
        return _fallback_insights(dashboard_data)

    context = _prepare_dashboard_context(dashboard_data)

    user_prompt = f"""Analyze the following executive dashboard data and generate professional financial insights.

{context}

Generate insights based ONLY on the provided data. Be precise, factual, and decision-oriented."""

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=1500,
            response_format={"type": "json_object"},
        )

        output_txt = response.choices[0].message.content.strip()
        result = json.loads(output_txt)

        # Validate structure
        if "summary" not in result:
            result["summary"] = "Dashboard analysis complete."
        if "insights" not in result:
            result["insights"] = []
        if "recommendations" not in result:
            result["recommendations"] = []

        logger.info("Generated %d insights and %d recommendations",
                     len(result["insights"]), len(result["recommendations"]))
        return result

    except json.JSONDecodeError as e:
        logger.error("LLM returned invalid JSON for insights: %s", e)
        return _fallback_insights(dashboard_data)
    except Exception as e:
        logger.error("Failed to generate executive insights: %s", e)
        return _fallback_insights(dashboard_data)


def _fallback_insights(dashboard_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate basic rule-based insights when the LLM is unavailable.
    """
    kpis = dashboard_data.get("kpis", [])
    insights = []

    # Extract KPI values
    revenue_kpi = next((k for k in kpis if k["name"] == "Total Revenue"), None)
    cost_kpi = next((k for k in kpis if k["name"] == "Total Cost"), None)
    profit_kpi = next((k for k in kpis if k["name"] == "Gross Profit"), None)
    margin_kpi = next((k for k in kpis if k["name"] == "Profit Margin"), None)

    if margin_kpi:
        margin_val = margin_kpi.get("raw_value", 0)
        if margin_val > 20:
            assessment = "strong"
        elif margin_val > 10:
            assessment = "moderate"
        else:
            assessment = "weak"
        insights.append({
            "type": "profitability",
            "title": f"Profit Margin: {margin_kpi['value']}",
            "description": f"The profit margin of {margin_kpi['value']} indicates {assessment} profitability.",
            "confidence": "high",
        })

    if revenue_kpi and cost_kpi:
        rev = revenue_kpi.get("raw_value", 0)
        cost = cost_kpi.get("raw_value", 0)
        cost_ratio = (cost / rev * 100) if rev else 0
        insights.append({
            "type": "cost",
            "title": f"Cost-to-Revenue Ratio: {cost_ratio:.1f}%",
            "description": f"Total cost of {cost_kpi['value']} represents {cost_ratio:.1f}% of revenue ({revenue_kpi['value']}).",
            "confidence": "high",
        })

    # Section-level insights
    sections = dashboard_data.get("sections", [])
    for section in sections[:3]:
        data = section.get("data", [])
        if data and len(data) >= 2:
            y_key = section.get("y_key", "value")
            top = data[0]
            insights.append({
                "type": "performance",
                "title": section["title"],
                "description": f"Top performer: {list(top.values())[0]} with {y_key} of {list(top.values())[-1]:,.0f}.",
                "confidence": "medium",
            })

    summary = "Dashboard analysis generated using rule-based engine (LLM unavailable)."
    if revenue_kpi:
        summary = f"Total revenue is {revenue_kpi['value']}."
        if profit_kpi:
            summary += f" Gross profit stands at {profit_kpi['value']}."
        if margin_kpi:
            summary += f" Profit margin is {margin_kpi['value']}."

    return {
        "summary": summary,
        "insights": insights,
        "recommendations": [
            {
                "action": "Review cost structure for optimization opportunities",
                "reason": "Detailed cost analysis requires deeper investigation into segment-level data.",
            }
        ],
    }
