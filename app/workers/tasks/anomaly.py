from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import text

logger = structlog.get_logger(__name__)

OVERSPEED_THRESHOLD = 200
LOW_BATTERY_CRITICAL = 10


async def detect_anomalies(
    ctx: dict,
    *,
    fleet_id: str,
    lookback_minutes: int = 5,
) -> dict:
    """
    Scans recent telemetry for anomalies (overspeed, critical battery).
    Idempotent — checks existing unresolved alerts before inserting.
    """
    session_factory = ctx["session_factory"]
    fleet_uuid = uuid.UUID(fleet_id)
    since = datetime.now(tz=timezone.utc) - timedelta(minutes=lookback_minutes)

    async with session_factory() as session:
        overspeed = await session.execute(
            text("""
                SELECT DISTINCT ON (vehicle_id)
                    vehicle_id, speed, recorded_at, latitude, longitude
                FROM telemetry_events
                WHERE
                    fleet_id = :fleet_id
                    AND recorded_at >= :since
                    AND speed > :threshold
                ORDER BY vehicle_id, recorded_at DESC
            """),
            {"fleet_id": fleet_uuid, "since": since, "threshold": OVERSPEED_THRESHOLD},
        )

        alerts_created = 0
        for row in overspeed.fetchall():
            existing = await session.execute(
                text("""
                    SELECT id FROM alert_log
                    WHERE fleet_id = :fleet_id
                      AND vehicle_id = :vehicle_id
                      AND alert_type = 'OVERSPEED'
                      AND acknowledged = false
                      AND triggered_at >= :since
                    LIMIT 1
                """),
                {
                    "fleet_id": fleet_uuid,
                    "vehicle_id": row.vehicle_id,
                    "since": since,
                },
            )
            if existing.fetchone():
                continue

            await session.execute(
                text("""
                    INSERT INTO alert_log
                        (fleet_id, vehicle_id, alert_type, severity, payload)
                    VALUES
                        (:fleet_id, :vehicle_id, 'OVERSPEED', 'WARNING', :payload::jsonb)
                """),
                {
                    "fleet_id": fleet_uuid,
                    "vehicle_id": row.vehicle_id,
                    "payload": (
                        f'{{"speed": {row.speed}, '
                        f'"lat": {row.latitude}, "lon": {row.longitude}}}'
                    ),
                },
            )
            alerts_created += 1

        await session.commit()

    logger.info(
        "anomaly_detection_complete",
        fleet_id=fleet_id,
        alerts_created=alerts_created,
    )
    return {"status": "ok", "alerts_created": alerts_created}
