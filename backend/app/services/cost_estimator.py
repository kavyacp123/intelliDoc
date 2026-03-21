import hashlib
import json
from app.models.intent import QueryIntent
from app.services.cost_model import get_learned_cost

def hash_intent(intent: QueryIntent) -> str:
    """Deteministic hash of the analytical intent."""
    data = {
        "m": intent.metric,
        "o": intent.operation,
        "g": intent.group_by,
        "f": intent.filters,
        "t": intent.time_grain
    }
    return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()

def estimate_cost(intent: QueryIntent, metadata: dict) -> float:
    """
    Evaluates algorithmic complexity of a targeted query path natively.
    Combines learned costs with cardinality heuristics.
    """
    # Check for adaptive learned cost first
    intent_hash = hash_intent(intent)
    learned = get_learned_cost(intent_hash)
    if learned:
        return learned * 1000  # Scale duration to a cost score (heuristic)

    row_count = metadata.get("row_count", 0)
    cost = float(row_count)

    # Cardinality factor (High distinct counts = higher cost)
    if intent.group_by:
        col = intent.group_by[0]
        stats = metadata.get("column_stats", {}).get(col, {})
        distinct = stats.get("distinct", 0)
        
        if distinct > 0:
            # Scale cost based on groupings (1.0 factor for 10 unique values)
            cost *= (distinct / 10.0)

    # Operation penalty
    if intent.operation == "top_n":
        cost *= 1.5

    # Pre-aggregation bonus (applied only if plan table is pre-aggregated)
    is_pre_agg = metadata.get("is_pre_agg", False)
    if is_pre_agg:
        cost *= 0.1

    # Time-based partition bonus
    if intent.time_grain:
        cost *= 0.5

    return cost
