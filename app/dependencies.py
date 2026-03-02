from __future__ import annotations
from typing import AsyncGenerator

import structlog
from redis.asyncio import Redis, ConnectionPool
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.rate_limiter import TokenBucketRateLimiter
from app.db.engine import AsyncSessionLocal, AsyncSessionReplica
from app.repositories.telemetry import TelemetryRepository
from app.services.analytics import AnalyticsService
from app.services.cache import CacheService
from app.services.telemetry import TelemetryService

logger = structlog.get_logger(__name__)

_redis_pool: ConnectionPool | None = None


def set_redis_pool(pool: ConnectionPool) -> None:
    global _redis_pool
    _redis_pool = pool


def get_redis() -> Redis:
    if _redis_pool is None:
        raise RuntimeError("Redis pool not initialized")
    return Redis(connection_pool=_redis_pool)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_replica_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionReplica() as session:
        yield session


def get_telemetry_service(session: AsyncSession, redis: Redis) -> TelemetryService:
    repo = TelemetryRepository(session)
    rate_limiter = TokenBucketRateLimiter(
        redis=redis,
        capacity=settings.rate_limit_requests,
        refill_rate=settings.rate_limit_requests / settings.rate_limit_window_seconds,
    )
    return TelemetryService(repository=repo, rate_limiter=rate_limiter)


def get_analytics_service(session: AsyncSession, redis: Redis) -> AnalyticsService:
    repo = TelemetryRepository(session)
    cache = CacheService(redis)
    return AnalyticsService(repository=repo, cache=cache)
