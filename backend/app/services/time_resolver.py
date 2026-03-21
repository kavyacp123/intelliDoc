from app.models.intent import QueryIntent

def resolve_time(intent: QueryIntent, schema: dict) -> str:
    """Convert time_grain into a valid SQL DATE_TRUNC or EXTRACT expression based on actual schema date bindings."""
    time_dims = schema.get("time_dimensions", [])
    
    # Fallback if no explicit time_dimensions provided by the schema builder
    date_col = time_dims[0] if time_dims else "date"
    intent.resolved_time_column = date_col
    
    if intent.time_grain == "year":
        return f"EXTRACT(YEAR FROM {date_col})"
        
    if intent.time_grain == "month":
        return f"DATE_TRUNC('month', {date_col})"
        
    if intent.time_grain == "day":
        return f"DATE_TRUNC('day', {date_col})"
        
    # If no explicit time grain but we are trending, default to truncated month
    if intent.operation == "trend":
        return f"DATE_TRUNC('month', {date_col})"
        
    return date_col
