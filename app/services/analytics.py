"""app/services/analytics.py

Analytics service — orchestrates repository queries, caching, and response assembly.

v3 additions:
  - get_scenario_events: fleet-scoped paginated scenario filter with caching
  - get_scenario_summary: per-label counts with caching
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog

from app.config import settings
from app.observability.metrics import cache_hits, cache_misses
from app.repositories.telemetry import TelemetryRepository
from app.schemas.analytics import (
    FleetSummaryResponse,
    HourlyStatEntry,
    LowBatteryAlert,
    ScenarioEventItem,
    ScenarioEventsResponse,
    ScenarioSummaryResponse,
)
from app.services.cache import CacheService

logger = structlog.get_logger(__name__)

# Short TTL for scenario data — these are append-only event queries.
_SCENARIO_EVENTS_TTL: int = 30
_SCENARIO_SUMMARY_TTL: int = 60


class AnalyticsService:
    def __init__(
        self,
        repository: TelemetryRepository,
        cache: CacheService,
    ) -> None:
        self._repo = repository
        self._cache = cache

    # ------------------------------------------------------------------
    # Existing analytics methods (unchanged)
    # ------------------------------------------------------------------

    async def get_fleet_summary(self, fleet_id: uuid.UUID) -> FleetSummaryResponse:
        cache_key = f"cache:fleet_summary:{fleet_id}"
        endpoint = "fleet_summary"

        cached = await self._cache.get(cache_key)
        if cached is not None:
            cache_hits.labels(endpoint=endpoint).inc()
            return FleetSummaryResponse(**cached)

        cache_misses.labels(endpoint=endpoint).inc()
        raw = await self._repo.get_fleet_summary_raw(fleet_id)

        response = FleetSummaryResponse(
            fleet_id=fleet_id,
            total_vehicles=raw.get("total_vehicles", 0),
            active_vehicles_last_hour=raw.get("active_vehicles_last_hour", 0),
            avg_speed_last_hour=raw.get("avg_speed_last_hour"),
            low_battery_count=raw.get("low_battery_count", 0),
            generated_at=datetime.now(tz=timezone.utc),
        )

        await self._cache.set(
            cache_key,
            response.model_dump(),
            ttl=settings.cache_ttl_fleet_summary,
        )
        return response

    async def get_low_battery_alerts(
        self, fleet_id: uuid.UUID, threshold: int = 20
    ) -> list[LowBatteryAlert]:
        cache_key = f"cache:low_battery:{fleet_id}:{threshold}"
        endpoint = "low_battery"

        cached = await self._cache.get(cache_key)
        if cached is not None:
            cache_hits.labels(endpoint=endpoint).inc()
            return [LowBatteryAlert(**item) for item in cached]

        cache_misses.labels(endpoint=endpoint).inc()
        raw = await self._repo.get_low_battery_vehicles(fleet_id, threshold)
        alerts = [LowBatteryAlert(**item) for item in raw]

        await self._cache.set(
            cache_key,
            [a.model_dump() for a in alerts],
            ttl=settings.cache_ttl_low_battery,
        )
        return alerts

    async def get_hourly_stats(
        self,
        fleet_id: uuid.UUID,
        vehicle_id: uuid.UUID,
        hours: int = 24,
    ) -> list[HourlyStatEntry]:
        cache_key = f"cache:hourly_stats:{fleet_id}:{vehicle_id}:{hours}"
        endpoint = "hourly_stats"

        cached = await self._cache.get(cache_key)
        if cached is not None:
            cache_hits.labels(endpoint=endpoint).inc()
            return [HourlyStatEntry(**item) for item in cached]

        cache_misses.labels(endpoint=endpoint).inc()
        since = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
        raw = await self._repo.get_hourly_avg_speed(fleet_id, vehicle_id, since)
        entries = [HourlyStatEntry(**item) for item in raw]

        await self._cache.set(
            cache_key,
            [e.model_dump() for e in entries],
            ttl=settings.cache_ttl_hourly_stats,
        )
        return entries

    # ------------------------------------------------------------------
    # v3 — Scenario analytics methods
    # ------------------------------------------------------------------

    async def get_scenario_events(
        self,
        fleet_id: uuid.UUID,
        scenario: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> ScenarioEventsResponse:
        """Return paginated telemetry events matching a scenario tag.

        Cache key includes all filter dimensions so each unique query window
        gets its own cache entry.  TTL is short because new events arrive
        continuously.

        Args:
            fleet_id: Fleet to scope the query to.
            scenario: Scenario label (e.g. "hard_brake").
            from_date / to_date: Optional time range bounds.
            limit / offset: Pagination controls.
        """
        cache_key = (
            f"cache:scenario_events:{fleet_id}:{scenario}"
            f":{from_date}:{to_date}:{limit}:{offset}"
        )
        endpoint = "scenario_events"

        cached = await self._cache.get(cache_key)
        if cached is not None:
            cache_hits.labels(endpoint=endpoint).inc()
            return ScenarioEventsResponse(**cached)

        cache_misses.labels(endpoint=endpoint).inc()

        total, rows = await self._repo.get_scenario_events(
            fleet_id=fleet_id,
            scenario=scenario,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )

        results = [
            ScenarioEventItem(
                event_id=row.id,
                vehicle_id=row.vehicle_id,
                recorded_at=row.recorded_at,
                speed=row.speed,
                battery_level=row.battery_level,
                acceleration=row.acceleration,
                weather=row.weather,
                scenarios=row.scenarios or [],
            )
            for row in rows
        ]

        response = ScenarioEventsResponse(
            fleet_id=fleet_id,
            scenario=scenario,
            total=total,
            limit=limit,
            offset=offset,
            results=results,
        )

        await self._cache.set(
            cache_key,
            response.model_dump(),
            ttl=_SCENARIO_EVENTS_TTL,
        )
        return response

    async def get_scenario_summary(
        self,
        fleet_id: uuid.UUID,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> ScenarioSummaryResponse:
        """Return count of events per scenario label for a fleet.

        Uses jsonb_array_elements_text in the repository layer so all
        label counting happens in Postgres — no Python-level aggregation.

        Args:
            fleet_id: Fleet to summarize.
            from_date / to_date: Optional time range.
        """
        cache_key = f"cache:scenario_summary:{fleet_id}:{from_date}:{to_date}"
        endpoint = "scenario_summary"

        cached = await self._cache.get(cache_key)
        if cached is not None:
            cache_hits.labels(endpoint=endpoint).inc()
            return ScenarioSummaryResponse(**cached)

        cache_misses.labels(endpoint=endpoint).inc()

        summary = await self._repo.get_scenario_summary(
            fleet_id=fleet_id,
            from_date=from_date,
            to_date=to_date,
        )

        response = ScenarioSummaryResponse(
            fleet_id=fleet_id,
            from_date=from_date,
            to_date=to_date,
            summary=summary,
        )

        await self._cache.set(
            cache_key,
            response.model_dump(),
            ttl=_SCENARIO_SUMMARY_TTL,
        )
        return response
