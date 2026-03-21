"""
Insight Generation Engine (V4).

Converts raw analytical results into human-readable business insights.
"""

from app.models.intent import QueryIntent

def generate_insights(data: list, intent: QueryIntent) -> list:
    """
    Derive business-level insights from result set based on intent.
    """
    insights = []
    if not data:
        return ["No significant trends found in the selected range."]

    # 1. Market Leader Insight
    if intent.operation == "top_n" and len(data) > 0:
        top_row = data[0]
        # Common keys are often 'dimension', 'total', etc.
        # We look for the first non-metric column as the dimension name
        dim_val = "N/A"
        for k, v in top_row.items():
            if k not in ("total", "rank_n", "tenant_id"):
                dim_val = v
                break
        
        val = top_row.get("total", 0)
        insights.append(f"Performance Leader: {dim_val} is currently outperforming others with a total of {val:,.2f}.")

    # 2. Pareto/Concentration Insight
    if len(data) > 1 and intent.operation in ("top_n", "aggregate"):
        total_sum = sum(row.get("total", 0) for row in data if "total" in row)
        if total_sum > 0:
            top_share = (data[0].get("total", 0) / total_sum) * 100
            if top_share > 50:
                insights.append(f"High Concentration: The top category accounts for {top_share:.1f}% of the total volume.")

    # 3. Trajectory Insight for Trends
    if intent.operation == "trend" and len(data) >= 2:
        first_val = data[0].get("total", 0)
        last_val = data[-1].get("total", 0)
        delta = last_val - first_val
        percent = (delta / first_val * 100) if first_val != 0 else 0
        
        direction = "upward" if delta > 0 else "downward"
        insights.append(f"Trend Trajectory: Observed a {abs(percent):.1f}% {direction} shift over the period.")

    return insights
