"""app/api/v1/analytics.py

Analytics API endpoints.

v3 additions:
  GET /analytics/fleet/{fleet_id}/scenarios?scenario=hard_brake
  GET /analytics/fleet/{fleet_id}/scenario-summary
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_analytics_service, get_redis, get_replica_session
from app.domain.scenarios import all_scenario_labels
from app.schemas.analytics import (
    FleetSummaryResponse,
    HourlyStatEntry,
    LowBatteryAlert,
    ScenarioEventsResponse,
    ScenarioSummaryResponse,
)
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Pre-compute valid scenario labels at import time for O(1) validation.
_VALID_SCENARIOS = all_scenario_labels()


def _build_service(
    session: AsyncSession = Depends(get_replica_session),
    redis: Redis = Depends(get_redis),
) -> AnalyticsService:
    return get_analytics_service(session, redis)


# ------------------------------------------------------------------
# Existing endpoints (unchanged)
# ------------------------------------------------------------------

@router.get("/fleet/{fleet_id}/summary", response_model=FleetSummaryResponse)
async def fleet_summary(
    fleet_id: uuid.UUID,
    service: Annotated[AnalyticsService, Depends(_build_service)],
) -> FleetSummaryResponse:
    return await service.get_fleet_summary(fleet_id)


@router.get("/fleet/{fleet_id}/low-battery", response_model=list[LowBatteryAlert])
async def low_battery_alerts(
    fleet_id: uuid.UUID,
    threshold: Annotated[int, Query(ge=1, le=100)] = 20,
    service: Annotated[AnalyticsService, Depends(_build_service)] = ...,
) -> list[LowBatteryAlert]:
    return await service.get_low_battery_alerts(fleet_id, threshold)


@router.get(
    "/vehicle/{fleet_id}/{vehicle_id}/hourly",
    response_model=list[HourlyStatEntry],
)
async def hourly_stats(
    fleet_id: uuid.UUID,
    vehicle_id: uuid.UUID,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
    service: Annotated[AnalyticsService, Depends(_build_service)] = ...,
) -> list[HourlyStatEntry]:
    return await service.get_hourly_stats(fleet_id, vehicle_id, hours)


# ------------------------------------------------------------------
# v3 — Scenario analytics endpoints
# ------------------------------------------------------------------

@router.get(
    "/fleet/{fleet_id}/scenarios",
    response_model=ScenarioEventsResponse,
    summary="Get events by scenario tag",
    description=(
        "Returns paginated telemetry events for a fleet where the `scenarios` "
        "JSONB column contains the requested tag. Uses a GIN index for O(log n) "
        "containment lookups via the PostgreSQL @> operator."
    ),
)
async def fleet_scenario_events(
    fleet_id: uuid.UUID,
    service: Annotated[AnalyticsService, Depends(_build_service)],
    scenario: Annotated[
        str,
        Query(description=f"Scenario tag. Valid values: {sorted(_VALID_SCENARIOS)}"),
    ],
    from_date: Annotated[
        Optional[datetime],
        Query(description="Filter events on or after this UTC datetime (ISO-8601)."),
    ] = None,
    to_date: Annotated[
        Optional[datetime],
        Query(description="Filter events before this UTC datetime (ISO-8601)."),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ScenarioEventsResponse:
    # Validate against the rule registry — fast reject before hitting DB.
    if scenario not in _VALID_SCENARIOS:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "msg": f"Unknown scenario '{scenario}'.",
                "valid_values": sorted(_VALID_SCENARIOS),
            },
        )

    return await service.get_scenario_events(
        fleet_id=fleet_id,
        scenario=scenario,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/fleet/{fleet_id}/scenario-summary",
    response_model=ScenarioSummaryResponse,
    summary="Get scenario event counts for a fleet",
    description=(
        "Returns a count of events per scenario label for the fleet, optionally "
        "filtered by time range. Uses jsonb_array_elements_text in Postgres — "
        "all aggregation happens in the database."
    ),
)
async def fleet_scenario_summary(
    fleet_id: uuid.UUID,
    service: Annotated[AnalyticsService, Depends(_build_service)],
    from_date: Annotated[
        Optional[datetime],
        Query(description="Count events on or after this UTC datetime (ISO-8601)."),
    ] = None,
    to_date: Annotated[
        Optional[datetime],
        Query(description="Count events before this UTC datetime (ISO-8601)."),
    ] = None,
) -> ScenarioSummaryResponse:
    return await service.get_scenario_summary(
        fleet_id=fleet_id,
        from_date=from_date,
        to_date=to_date,
    )
