from __future__ import annotations
import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AggregateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_hourly_aggregates(
        self,
        fleet_id: uuid.UUID,
        vehicle_id: uuid.UUID,
        since: datetime,
    ) -> list[dict]:
        stmt = text("""
            SELECT
                hour_bucket,
                avg_speed,
                max_speed,
                min_battery,
                event_count,
                computed_at
            FROM hourly_aggregates
            WHERE
                fleet_id   = :fleet_id
                AND vehicle_id = :vehicle_id
                AND hour_bucket >= :since
            ORDER BY hour_bucket DESC
        """)
        result = await self._session.execute(
            stmt,
            {"fleet_id": fleet_id, "vehicle_id": vehicle_id, "since": since},
        )
        return [dict(row._mapping) for row in result.fetchall()]
