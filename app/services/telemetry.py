"""app/services/telemetry.py

Ingestion service — rate limiting, scenario detection, persistence, job enqueue.

v3 change: imports detect_scenarios from app.domain.scenarios (canonical location).
"""
from __future__ import annotations

import structlog
from arq import create_pool
from arq.connections import RedisSettings

from app.config import settings
from app.core.exceptions import RateLimitExceededError
from app.core.rate_limiter import TokenBucketRateLimiter
from app.domain.scenarios import detect_scenarios
from app.observability.metrics import ingestion_latency, ingestion_total
from app.repositories.telemetry import TelemetryRepository
from app.schemas.telemetry import TelemetryIngestRequest, TelemetryIngestResponse

logger = structlog.get_logger(__name__)


class TelemetryService:
    def __init__(
        self,
        repository: TelemetryRepository,
        rate_limiter: TokenBucketRateLimiter,
    ) -> None:
        self._repo = repository
        self._rate_limiter = rate_limiter

    async def ingest(self, payload: TelemetryIngestRequest) -> TelemetryIngestResponse:
        """Ingest a single telemetry event.

        Pipeline:
          1. Rate-limit check (Redis token bucket).
          2. Scenario detection (pure CPU, synchronous — no await needed).
          3. DB insert with detected scenarios.
          4. Enqueue background aggregation job (non-blocking, failure-safe).

        Args:
            payload: Validated ingest request from the API layer.

        Raises:
            RateLimitExceededError: If the fleet has exhausted its token bucket.
        """
        with ingestion_latency.time():
            allowed = await self._rate_limiter.is_allowed(str(payload.fleet_id))
            if not allowed:
                ingestion_total.labels(
                    fleet_id=str(payload.fleet_id), status="rate_limited"
                ).inc()
                raise RateLimitExceededError(payload.fleet_id)

            # Scenario detection is pure CPU — runs inline, no I/O.
            scenarios = detect_scenarios(payload)

            event_id = await self._repo.insert_event_with_scenarios(
                payload, scenarios=scenarios
            )
            await self._enqueue_aggregation_job(payload)

            ingestion_total.labels(
                fleet_id=str(payload.fleet_id), status="success"
            ).inc()

            logger.info(
                "telemetry_ingested",
                event_id=str(event_id),
                fleet_id=str(payload.fleet_id),
                vehicle_id=str(payload.vehicle_id),
                battery_level=payload.battery_level,
                scenarios=scenarios,
            )

            return TelemetryIngestResponse(
                event_id=event_id,
                recorded_at=payload.recorded_at,
                scenarios=scenarios,
            )

    async def _enqueue_aggregation_job(self, payload: TelemetryIngestRequest) -> None:
        """Enqueue a background hourly aggregation job.

        Failures are swallowed with a warning — job enqueue is best-effort
        and must never fail an otherwise successful ingestion.
        """
        try:
            redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
            pool = await create_pool(redis_settings)
            await pool.enqueue_job(
                "aggregate_hourly",
                fleet_id=str(payload.fleet_id),
                vehicle_id=str(payload.vehicle_id),
                hour=payload.recorded_at.replace(
                    minute=0, second=0, microsecond=0
                ).isoformat(),
            )
            await pool.aclose()
        except Exception as exc:
            logger.warning("job_enqueue_failed", error=str(exc))
