"""app/schemas/analytics.py

Pydantic response schemas for the analytics API layer.

v3 additions:
  - ScenarioEventItem: single event in a scenario search result
  - ScenarioEventsResponse: paginated wrapper for scenario event queries
  - ScenarioSummaryResponse: per-label counts for a fleet
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class HourlyStatEntry(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: float})

    hour_bucket: datetime
    avg_speed: Optional[Decimal]
    max_speed: Optional[Decimal]
    event_count: int


class FleetSummaryResponse(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: float})

    fleet_id: uuid.UUID
    total_vehicles: int
    active_vehicles_last_hour: int
    avg_speed_last_hour: Optional[Decimal]
    low_battery_count: int
    generated_at: datetime


class LowBatteryAlert(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: float})

    vehicle_id: uuid.UUID
    battery_level: int
    last_seen: datetime
    latitude: Decimal
    longitude: Decimal


# ---------------------------------------------------------------------------
# v3 — Scenario analytics schemas
# ---------------------------------------------------------------------------

class ScenarioEventItem(BaseModel):
    """A single telemetry event matched by a scenario filter query."""

    model_config = ConfigDict(json_encoders={Decimal: float})

    event_id: uuid.UUID
    vehicle_id: uuid.UUID
    recorded_at: datetime
    speed: Decimal
    battery_level: int
    acceleration: Optional[Decimal]
    weather: Optional[str]
    scenarios: list[str]


class ScenarioEventsResponse(BaseModel):
    """Paginated response for GET /analytics/fleet/{id}/scenarios."""

    fleet_id: uuid.UUID
    scenario: str
    total: int = Field(description="Total matching events before pagination")
    limit: int
    offset: int
    results: list[ScenarioEventItem]


class ScenarioSummaryResponse(BaseModel):
    """Per-scenario event counts for GET /analytics/fleet/{id}/scenario-summary.

    Example:
        {
          "fleet_id": "...",
          "from_date": "2026-01-01T00:00:00Z",
          "to_date": null,
          "summary": {
            "hard_brake": 23,
            "over_speeding": 15,
            "low_battery": 5
          }
        }
    """

    fleet_id: uuid.UUID
    from_date: Optional[datetime]
    to_date: Optional[datetime]
    summary: dict[str, int]
