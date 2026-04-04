from app.models.intent import MultiStepPlan

def resolve_time(plan: MultiStepPlan, schema: dict) -> None:
    """Resolve time columns for the plan."""
    time_dims = schema.get("time_dimensions", [])
    date_col = time_dims[0] if time_dims else "date"
    plan.resolved_time_column = date_col

