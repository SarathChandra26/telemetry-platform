"""app/repositories/telemetry.py

Data access layer for telemetry_events.

v3 additions:
  - get_scenario_events: paginated JSONB @> containment query
  - get_scenario_summary: per-label counts via jsonb_array_elements_text
  - insert_event_with_scenarios: passes scenarios as list (JSONB serializes natively)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Sequence

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telemetry import TelemetryEvent
from app.schemas.telemetry import TelemetryIngestRequest

logger = structlog.get_logger(__name__)


class TelemetryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    async def insert_event(self, payload: TelemetryIngestRequest) -> uuid.UUID:
        """Backward-compatible shim — delegates to insert_event_with_scenarios."""
        return await self.insert_event_with_scenarios(payload, scenarios=[])

    async def insert_event_with_scenarios(
        self,
        payload: TelemetryIngestRequest,
        scenarios: list[str],
    ) -> uuid.UUID:
        """Persist a single telemetry event with pre-computed scenario tags.

        Args:
            payload:   Validated ingest request including optional enrichment fields.
            scenarios: Labels produced by the domain scenario engine.

        Returns:
            UUID of the newly inserted row.
        """
        event_id = uuid.uuid4()
        stmt = pg_insert(TelemetryEvent).values(
            id=event_id,
            fleet_id=payload.fleet_id,
            vehicle_id=payload.vehicle_id,
            speed=payload.speed,
            latitude=payload.latitude,
            longitude=payload.longitude,
            battery_level=payload.battery_level,
            recorded_at=payload.recorded_at,
            acceleration=payload.acceleration,
            weather=payload.weather,
            engine_on=payload.engine_on,
            scenarios=scenarios,
        )
        await self._session.execute(stmt)
        await self._session.commit()
        logger.debug(
            "telemetry_event_inserted",
            event_id=str(event_id),
            fleet_id=str(payload.fleet_id),
            vehicle_id=str(payload.vehicle_id),
            scenarios=scenarios,
        )
        return event_id

    # ------------------------------------------------------------------
    # Scenario queries (v3)
    # ------------------------------------------------------------------

    async def get_scenario_events(
        self,
        fleet_id: uuid.UUID,
        scenario: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[int, Sequence[TelemetryEvent]]:
        """Return paginated events where scenarios @> [scenario] for a fleet.

        The JSONB @> operator is accelerated by the GIN index from migration
        b5f83d2e7c1a. SQLAlchemy's JSONB .contains() emits the @> operator.

        Returns:
            Tuple of (total_count, rows).
        """
        limit = min(limit, 500)

        base = (
            select(TelemetryEvent)
            .where(TelemetryEvent.fleet_id == fleet_id)
            .where(TelemetryEvent.scenarios.contains([scenario]))
        )

        if from_date is not None:
            base = base.where(TelemetryEvent.recorded_at >= from_date)
        if to_date is not None:
            base = base.where(TelemetryEvent.recorded_at < to_date)

        count_stmt = select(func.count()).select_from(base.subquery())
        total: int = (await self._session.execute(count_stmt)).scalar_one()

        data_stmt = (
            base
            .order_by(TelemetryEvent.recorded_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(data_stmt)).scalars().all()
        return total, rows

    async def get_scenario_summary(
        self,
        fleet_id: uuid.UUID,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> dict[str, int]:
        """Return per-scenario event counts for a fleet.

        Uses jsonb_array_elements_text to unnest the scenarios JSONB array
        per row, then groups and counts. The GIN index is used for the
        initial non-empty filter.

        Returns:
            dict mapping scenario label to count, e.g.
            {"hard_brake": 23, "over_speeding": 15, "low_battery": 5}
        """
        params: dict[str, Any] = {"fleet_id": fleet_id}
        time_filters = ""

        if from_date is not None:
            params["from_date"] = from_date
            time_filters += " AND recorded_at >= :from_date"
        if to_date is not None:
            params["to_date"] = to_date
            time_filters += " AND recorded_at < :to_date"

        stmt = text(f"""
            SELECT
                scenario_label,
                COUNT(*) AS event_count
            FROM telemetry_events,
                 jsonb_array_elements_text(scenarios) AS scenario_label
            WHERE
                fleet_id = :fleet_id
                AND jsonb_array_length(scenarios) > 0
                {time_filters}
            GROUP BY scenario_label
            ORDER BY event_count DESC
        """)

        result = await self._session.execute(stmt, params)
        return {row.scenario_label: row.event_count for row in result.fetchall()}

    # ------------------------------------------------------------------
    # Existing analytics queries (unchanged)
    # ------------------------------------------------------------------

    async def get_latest_event_per_vehicle(
        self, fleet_id: uuid.UUID
    ) -> Sequence[TelemetryEvent]:
        stmt = (
            select(TelemetryEvent)
            .where(TelemetryEvent.fleet_id == fleet_id)
            .distinct(TelemetryEvent.vehicle_id)
            .order_by(TelemetryEvent.vehicle_id, TelemetryEvent.recorded_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_hourly_avg_speed(
        self,
        fleet_id: uuid.UUID,
        vehicle_id: uuid.UUID,
        since: datetime,
    ) -> list[dict]:
        stmt = text("""
            SELECT
                date_trunc('hour', recorded_at) AS hour_bucket,
                ROUND(AVG(speed)::numeric, 2)   AS avg_speed,
                MAX(speed)                       AS max_speed,
                COUNT(*)                         AS event_count
            FROM telemetry_events
            WHERE
                fleet_id   = :fleet_id
                AND vehicle_id = :vehicle_id
                AND recorded_at >= :since
            GROUP BY hour_bucket
            ORDER BY hour_bucket DESC
        """)
        result = await self._session.execute(
            stmt, {"fleet_id": fleet_id, "vehicle_id": vehicle_id, "since": since}
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def get_low_battery_vehicles(
        self, fleet_id: uuid.UUID, threshold: int = 20
    ) -> list[dict]:
        stmt = text("""
            SELECT DISTINCT ON (vehicle_id)
                vehicle_id,
                battery_level,
                recorded_at AS last_seen,
                latitude,
                longitude
            FROM telemetry_events
            WHERE
                fleet_id = :fleet_id
                AND battery_level < :threshold
            ORDER BY vehicle_id, recorded_at DESC
        """)
        result = await self._session.execute(
            stmt, {"fleet_id": fleet_id, "threshold": threshold}
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def get_fleet_summary_raw(self, fleet_id: uuid.UUID) -> dict:
        one_hour_ago = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        stmt = text("""
            SELECT
                COUNT(DISTINCT vehicle_id)                           AS total_vehicles,
                COUNT(DISTINCT CASE
                    WHEN recorded_at >= :one_hour_ago THEN vehicle_id
                END)                                                 AS active_vehicles_last_hour,
                ROUND(AVG(CASE
                    WHEN recorded_at >= :one_hour_ago THEN speed
                END)::numeric, 2)                                    AS avg_speed_last_hour,
                COUNT(DISTINCT CASE
                    WHEN battery_level < 20 THEN vehicle_id
                END)                                                 AS low_battery_count
            FROM telemetry_events
            WHERE fleet_id = :fleet_id
        """)
        result = await self._session.execute(
            stmt, {"fleet_id": fleet_id, "one_hour_ago": one_hour_ago}
        )
        row = result.fetchone()
        return dict(row._mapping) if row else {}
