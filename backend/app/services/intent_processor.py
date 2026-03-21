from app.models.intent import QueryIntent

def enhance_intent(intent: QueryIntent, question: str, schema: dict) -> QueryIntent:
    """Hybrid Rule Engine: applies python rules explicitly to augment or override LLM intent."""
    q = question.lower()
    
    # Rule override (stronger than LLM)
    if any(word in q for word in ["top", "best", "highest"]):
        intent.operation = "top_n"
        
    if "trend" in q or "over time" in q:
        intent.operation = "trend"
        
    if "compare" in q or "vs" in q:
        intent.operation = "comparison"
        
    # Default metric resolution
    if not intent.metric:
        for m in ["revenue", "sales", "profit", "quantity", "gross_sales"]:
            if m in schema.get("metrics", []):
                intent.metric = m
                break
                
    # Default dimension
    if not intent.dimensions and schema.get("dimensions"):
        intent.dimensions = [schema.get("dimensions")[0]]
        
    # Default rank
    if intent.operation == "top_n" and not getattr(intent, 'rank', None):
        intent.rank = 1
        
    # Implicit time grain
    if not intent.time_grain and intent.operation == "trend":
        intent.time_grain = "month"
        
    if intent.group_by and not intent.time_grain:
        if "year" in intent.group_by:
            intent.time_grain = "year"
        elif "month" in intent.group_by:
            intent.time_grain = "month"

    return intent
