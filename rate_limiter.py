"""
Token bucket rate limiter using Redis Lua script for atomic check-and-decrement.
"""
from __future__ import annotations
import time
from redis.asyncio import Redis

RATE_LIMIT_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = 1

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or capacity
local last_refill = tonumber(bucket[2]) or now

local elapsed = now - last_refill
local refilled = math.min(capacity, tokens + elapsed * rate)

if refilled < cost then
    redis.call('HMSET', key, 'tokens', refilled, 'last_refill', now)
    redis.call('EXPIRE', key, 3600)
    return 0
else
    redis.call('HMSET', key, 'tokens', refilled - cost, 'last_refill', now)
    redis.call('EXPIRE', key, 3600)
    return 1
end
"""

class TokenBucketRateLimiter:
    def __init__(self,
        redis: Redis,
        capacity: int = 1000,
        refill_rate: float = 16.67,
    ) -> None:
        self._redis = redis
        self._capacity = capacity
        self._refill_rate = refill_rate

        # register_script is synchronous
        self._script = redis.register_script(RATE_LIMIT_LUA)

    async def is_allowed(self, fleet_id: str) -> bool:
        try:
            key = f"rate_limit:fleet:{fleet_id}"
            now = int(time.time())  # safer numeric type

            result = await self._script(
                keys=[key],
                args=[self._capacity, self._refill_rate, now],
            )
            return bool(result)

        except Exception:
            # Fail open — rate limiting outage should not kill ingestion
            return True
