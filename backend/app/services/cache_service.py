import hashlib
import json
import logging
from typing import Any, Optional

import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)

# Global redis client
_redis_client: Optional[redis.Redis] = None

async def get_redis() -> redis.Redis:
    """Get or initialize the Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client

def generate_cache_key(*args) -> str:
    """Generate a SHA256 hash from string arguments."""
    raw_str = "|".join(str(a) for a in args)
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

class CacheService:
    """3-Level Caching System using Redis."""
    
    DEFAULT_TTL = 300  # 5 minutes
    
    @staticmethod
    async def get(key: str) -> Optional[Any]:
        client = await get_redis()
        try:
            data = await client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning("Redis GET failed: %s", str(e))
        return None

    @staticmethod
    async def set(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
        client = await get_redis()
        try:
            await client.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.warning("Redis SET failed: %s", str(e))
            
    # ── Level 1: Intent Cache ──
    @classmethod
    async def get_intent(cls, user_id: str, table_name: str, question: str) -> Optional[dict]:
        key = f"intent:{generate_cache_key(user_id, table_name, question.lower().strip())}"
        return await cls.get(key)
        
    @classmethod
    async def set_intent(cls, user_id: str, table_name: str, question: str, intent_dict: dict) -> None:
        key = f"intent:{generate_cache_key(user_id, table_name, question.lower().strip())}"
        await cls.set(key, intent_dict)

    # ── Level 2: SQL Cache ──
    @classmethod
    async def get_sql(cls, intent_dict: dict) -> Optional[str]:
        # Hash intent dictionary deterministically by sorting keys
        intent_str = json.dumps(intent_dict, sort_keys=True)
        key = f"sql:{generate_cache_key(intent_str)}"
        return await cls.get(key)
        
    @classmethod
    async def set_sql(cls, intent_dict: dict, sql: str) -> None:
        intent_str = json.dumps(intent_dict, sort_keys=True)
        key = f"sql:{generate_cache_key(intent_str)}"
        await cls.set(key, sql)

    # ── Level 3: Result Cache ──
    @classmethod
    async def get_result(cls, sql: str, tenant_id: str) -> Optional[Any]:
        key = f"result:{generate_cache_key(sql, tenant_id)}"
        return await cls.get(key)
        
    @classmethod
    async def set_result(cls, sql: str, tenant_id: str, result: Any) -> None:
        key = f"result:{generate_cache_key(sql, tenant_id)}"
        await cls.set(key, result)
