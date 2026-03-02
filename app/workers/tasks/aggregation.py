from __future__ import annotations
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.aggregate import HourlyAggregate
from app.observability.metrics import worker_job_duration

logger = structlog.get_logger(__name__)


async def aggregate_hourly(
    ctx: dict,
    *,
    fleet_id: str,
    vehicle_id: str,
    hour: str,
) -> dict:
    """
    Idempotent aggregation job.
    Safe to run multiple times — ON CONFLICT DO UPDATE guarantees idempotency.
    """
    with worker_job_duration.labels(task_name="aggregate_hourly").time():
        session_factory = ctx["session_factory"]
        fleet_uuid = uuid.UUID(fleet_id)
        vehicle_uuid = uuid.UUID(vehicle_id)
        hour_dt = datetime.fromisoformat(hour).replace(tzinfo=timezone.utc)

        # Compute hour end boundary safely
        if hour_dt.hour < 23:
            hour_end = hour_dt.replace(hour=hour_dt.hour + 1)
        else:
            from datetime import timedelta
            hour_end = (hour_dt + timedelta(days=1)).replace(hour=0)

        async with session_factory() as session:
            raw = await session.execute(
                text("""
                    SELECT
                        ROUND(AVG(speed)::numeric, 2) AS avg_speed,
                        MAX(speed)                    AS max_speed,
                        MIN(battery_level)            AS min_battery,
                        COUNT(*)                      AS event_count
                    FROM telemetry_events
                    WHERE
                        fleet_id   = :fleet_id
                        AND vehicle_id = :vehicle_id
                        AND recorded_at >= :hour_start
                        AND recorded_at <  :hour_end
                """),
                {
                    "fleet_id": fleet_uuid,
                    "vehicle_id": vehicle_uuid,
                    "hour_start": hour_dt,
                    "hour_end": hour_end,
                },
            )
            row = raw.fetchone()
            if row is None or row.event_count == 0:
                logger.info("aggregate_hourly_no_data", fleet_id=fleet_id, hour=hour)
                return {"status": "no_data"}

            stmt = pg_insert(HourlyAggregate).values(
                fleet_id=fleet_uuid,
                vehicle_id=vehicle_uuid,
                hour_bucket=hour_dt,
                avg_speed=row.avg_speed,
                max_speed=row.max_speed,
                min_battery=row.min_battery,
                event_count=row.event_count,
                computed_at=datetime.now(tz=timezone.utc),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["fleet_id", "vehicle_id", "hour_bucket"],
                set_={
                    "avg_speed": stmt.excluded.avg_speed,
                    "max_speed": stmt.excluded.max_speed,
                    "min_battery": stmt.excluded.min_battery,
                    "event_count": stmt.excluded.event_count,
                    "computed_at": stmt.excluded.computed_at,
                },
            )
            await session.execute(stmt)
            await session.commit()

        # Invalidate cache
        try:
            from redis.asyncio import Redis
            from app.config import settings
            redis = Redis.from_url(str(settings.redis_url), decode_responses=True)
            await redis.delete(
                f"cache:fleet_summary:{fleet_id}",
                f"cache:hourly_stats:{fleet_id}:{vehicle_id}:24",
            )
            await redis.aclose()
        except Exception as exc:
            logger.warning("cache_invalidation_failed", error=str(exc))

        logger.info(
            "aggregate_hourly_complete",
            fleet_id=fleet_id,
            vehicle_id=vehicle_id,
            hour=hour,
            event_count=row.event_count,
        )
        return {"status": "ok", "event_count": row.event_count}
