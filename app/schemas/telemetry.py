from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TelemetryIngestRequest(BaseModel):
    fleet_id: uuid.UUID
    vehicle_id: uuid.UUID
    speed: Annotated[Decimal, Field(ge=0, le=500, decimal_places=2)]
    latitude: Annotated[Decimal, Field(ge=-90, le=90, decimal_places=6)]
    longitude: Annotated[Decimal, Field(ge=-180, le=180, decimal_places=6)]
    battery_level: Annotated[int, Field(ge=0, le=100)]
    recorded_at: datetime

    # ── v2 enrichment fields (all optional for backwards compatibility) ──
    acceleration: Optional[Decimal] = Field(
        default=None,
        description="Vehicle acceleration in m/s².  Negative values indicate deceleration.",
    )
    weather: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Weather condition at time of event (e.g. 'rainy', 'snowy', 'clear').",
    )
    engine_on: Optional[bool] = Field(
        default=None,
        description="Whether the vehicle engine was running at the time of the event.",
    )

    @field_validator("recorded_at")
    @classmethod
    def recorded_at_not_future(cls, v: datetime) -> datetime:
        now = datetime.now(tz=timezone.utc)
        if v.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")
        if v > now + timedelta(seconds=300):
            raise ValueError("recorded_at cannot be more than 5 minutes in the future")
        return v

    @model_validator(mode="after")
    def validate_coordinate_precision(self) -> TelemetryIngestRequest:
        if self.latitude == 0 and self.longitude == 0:
            raise ValueError("Coordinates (0, 0) are not valid telemetry data")
        return self


class TelemetryIngestResponse(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: float})

    event_id: uuid.UUID
    recorded_at: datetime
    scenarios: list[str] = Field(default_factory=list)
    status: str = "accepted"


class LatestEventResponse(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: float})

    vehicle_id: uuid.UUID
    speed: Decimal
    latitude: Decimal
    longitude: Decimal
    battery_level: int
    recorded_at: datetime


# ---------------------------------------------------------------------------
# Scenario search response models
# ---------------------------------------------------------------------------

class ScenarioEventResponse(BaseModel):
    """Single telemetry event returned from the scenario search endpoint."""

    model_config = ConfigDict(json_encoders={Decimal: float})

    event_id: uuid.UUID
    fleet_id: uuid.UUID
    vehicle_id: uuid.UUID
    recorded_at: datetime
    speed: Decimal
    battery_level: int
    acceleration: Optional[Decimal]
    weather: Optional[str]
    engine_on: Optional[bool]
    scenarios: list[str]


class ScenarioSearchResponse(BaseModel):
    """Paginated response envelope for GET /api/v1/scenarios."""

    total: int = Field(description="Total number of matching events (before pagination)")
    limit: int
    offset: int
    results: list[ScenarioEventResponse]
