from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.rate_limiter import TokenBucketRateLimiter


@pytest.mark.asyncio
async def test_allows_when_tokens_available():
    mock_redis = AsyncMock()
    mock_script = AsyncMock(return_value=1)
    # register_script is a sync method on redis.asyncio.Redis — use MagicMock
    mock_redis.register_script = MagicMock(return_value=mock_script)

    limiter = TokenBucketRateLimiter(redis=mock_redis, capacity=100, refill_rate=10.0)
    result = await limiter.is_allowed("fleet-abc")

    assert result is True
    mock_script.assert_awaited_once()


@pytest.mark.asyncio
async def test_denies_when_bucket_empty():
    mock_redis = AsyncMock()
    mock_script = AsyncMock(return_value=0)
    mock_redis.register_script = MagicMock(return_value=mock_script)

    limiter = TokenBucketRateLimiter(redis=mock_redis, capacity=100, refill_rate=10.0)
    result = await limiter.is_allowed("fleet-abc")

    assert result is False


@pytest.mark.asyncio
async def test_fails_open_on_redis_error():
    """When Redis is down, rate limiter should allow (fail open)."""
    mock_redis = AsyncMock()
    mock_script = AsyncMock(side_effect=ConnectionError("Redis down"))
    mock_redis.register_script = MagicMock(return_value=mock_script)

    limiter = TokenBucketRateLimiter(redis=mock_redis, capacity=100, refill_rate=10.0)
    result = await limiter.is_allowed("fleet-abc")

    assert result is True  # Fail open