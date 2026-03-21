from app.models.intent import QueryIntent

def resolve_metric(intent: QueryIntent, schema: dict) -> str:
    """Resolve ambiguous metrics deterministically."""
    metrics_list = schema.get("metrics", [])
    if not metrics_list:
        return intent.metric or "*"
        
    if intent.metric in metrics_list:
        intent.resolved_metric = intent.metric
        return intent.metric
        
    # Search for known standard fallbacks if requested metric is invalid/ambiguous
    for m in ["revenue", "sales", "profit", "gross_sales"]:
        if m in metrics_list:
            intent.resolved_metric = m
            return m
            
    # Default to the first valid metric
    intent.resolved_metric = metrics_list[0]
    return metrics_list[0]
