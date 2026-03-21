"""
Adaptive Cost Model (Feedback Loop).

Learns from real execution durations to override heuristic estimates.
"""

import logging
from app.core.config import settings
import redis

logger = logging.getLogger(__name__)

# Lazy Redis client — initialized on first use
_redis_client = None

def _get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            _redis_client.ping()
        except Exception as e:
            logger.warning("Redis unavailable for cost model: %s", e)
            _redis_client = None
    return _redis_client

def get_learned_cost(intent_hash: str) -> float | None:
    """
    Retrieve the historical actual execution time for a specific intent.
    """
    client = _get_redis()
    if not client:
        return None
    try:
        val = client.get(f"cost:{intent_hash}")
        return float(val) if val else None
    except Exception:
        return None

def update_cost_model(intent_hash: str, actual_time: float) -> None:
    """
    Record the actual execution time for an intent to aid future planning.
    """
    client = _get_redis()
    if not client:
        return
    try:
        client.set(f"cost:{intent_hash}", actual_time)
    except Exception:
        pass
