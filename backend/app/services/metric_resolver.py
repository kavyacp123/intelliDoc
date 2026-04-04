from app.models.intent import MultiStepPlan

def resolve_metric(plan: MultiStepPlan, schema: dict) -> None:
    """Resolve ambiguous metrics deterministically for each step."""
    metrics_list = schema.get("metrics", [])
    if not metrics_list:
        return
        
    for step in plan.steps:
        if not step.metric or step.metric == "*":
            continue
            
        if step.metric in metrics_list:
            continue
            
        # Search for known standard fallbacks if requested metric is invalid/ambiguous
        resolved = False
        for m in ["revenue", "sales", "gross_total", "net_total", "profit", "gross_sales", "value", "amount", "total"]:
            if m in metrics_list:
                step.metric = m
                resolved = True
                break
                
        # Default to the first valid metric
        if not resolved:
            step.metric = metrics_list[0]

