"""
Adaptive Cost Model (Feedback Loop).

Learns from real execution durations to override heuristic estimates.
"""

from app.core.config import settings
import redis

# Initialize Redis client
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

def get_learned_cost(intent_hash: str) -> float | None:
    """
    Retrieve the historical actual execution time for a specific intent.
    """
    val = redis_client.get(f"cost:{intent_hash}")
    return float(val) if val else None

def update_cost_model(intent_hash: str, actual_time: float) -> None:
    """
    Record the actual execution time for an intent to aid future planning.
    """
    # Simply store the latest duration (or could use EMA for smoothing)
    redis_client.set(f"cost:{intent_hash}", actual_time)
