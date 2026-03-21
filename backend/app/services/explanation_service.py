from app.models.intent import QueryIntent

def generate_explanation(intent: QueryIntent, plan: dict) -> dict:
    """
    Generates a user-facing explanation log mapping out internally utilized routing optimizations.
    """
    explanation = {
        "metric": intent.resolved_metric or intent.metric,
        "operation": intent.operation,
        "group_by": intent.group_by,
        "strategy": plan.get("strategy")
    }

    # Evaluate execution footprint mappings derived from the Query Planner natively
    if plan.get("used_pre_agg"):
        explanation["optimization"] = "Used pre-aggregated table for faster results"

    if plan.get("execution_mode") == "async":
        explanation["note"] = "Large dataset processed asynchronously"
        
    if plan.get("strategy") == "cache":
        explanation["optimization"] = "Instant read from query cache mapping"

    return explanation
