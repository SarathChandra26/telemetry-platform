"""app/services/cache.py

Redis-backed cache service with safe JSON serialization.

UUID serialization fix: Python's standard json module does not know how to
serialize uuid.UUID, datetime, or Decimal.  The _json_default hook handles
all three so callers never need to pre-serialize values before calling set().

This is critical for analytics responses that include UUID fleet_id / vehicle_id
fields returned by Pydantic's model_dump(), which returns native Python types
(not strings) by default.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = structlog.get_logger(__name__)


def _json_default(obj: Any) -> Any:
    """Fallback serializer for types not handled by json.JSONEncoder.

    Handles:
      - Decimal  → float  (speed, lat/lon precision fields)
      - UUID     → str    (fleet_id, vehicle_id, event_id)
      - datetime → ISO-8601 string (recorded_at, generated_at)

    Raises:
      TypeError: for any other non-serializable type, bubbling up clearly.
    """
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class CacheService:
    """Thin async wrapper around Redis providing typed get/set/delete operations.

    All methods are failure-safe: RedisError is caught and logged as a warning
    so a cache outage degrades to cache-miss behaviour without crashing the API.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get(self, key: str) -> Any | None:
        """Retrieve and deserialize a cached value.

        Returns None on cache miss or Redis error (both treated identically
        by callers — they fall through to the DB query).
        """
        try:
            raw = await self._redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except RedisError as exc:
            logger.warning("cache_get_failed", key=key, error=str(exc))
            return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """Serialize and store *value* with a TTL in seconds.

        Uses _json_default to handle UUID/datetime/Decimal fields that
        appear in Pydantic model_dump() output.
        """
        try:
            serialized = json.dumps(value, default=_json_default)
            await self._redis.set(key, serialized, ex=ttl)
        except RedisError as exc:
            logger.warning("cache_set_failed", key=key, error=str(exc))

    async def delete(self, key: str) -> None:
        try:
            await self._redis.delete(key)
        except RedisError as exc:
            logger.warning("cache_delete_failed", key=key, error=str(exc))

    async def delete_pattern(self, pattern: str) -> None:
        """Delete all keys matching a glob pattern.

        Uses SCAN to iterate without blocking Redis (avoids KEYS in production).
        """
        try:
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
                if keys:
                    await self._redis.delete(*keys)
                if cursor == 0:
                    break
        except RedisError as exc:
            logger.warning("cache_delete_pattern_failed", pattern=pattern, error=str(exc))
