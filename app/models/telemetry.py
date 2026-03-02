"""app/models/telemetry.py

SQLAlchemy ORM model for the partitioned telemetry_events table.

Partitioning: RANGE on recorded_at (monthly).
  New partitions are created by scripts/partition_manager.py at startup.

v3 change: scenarios column is now JSONB (was TEXT[] in v2).
  - Enables native @> containment queries accelerated by GIN index.
  - Stores scenario tags as a JSON array: ["hard_brake", "low_battery"]
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    UUID, Boolean, CheckConstraint, DateTime, Index,
    Numeric, SmallInteger, Text, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"
    __table_args__ = (
        CheckConstraint("speed >= 0 AND speed <= 500", name="ck_speed_range"),
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_lat_range"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_lon_range"),
        CheckConstraint("battery_level >= 0 AND battery_level <= 100", name="ck_battery_range"),
        Index("idx_telemetry_fleet_recorded", "fleet_id", "recorded_at"),
        Index("idx_telemetry_vehicle_recorded", "vehicle_id", "recorded_at"),
        # GIN index on scenarios JSONB and composite fleet+time index are
        # created via raw DDL in the Alembic migration (b5f83d2e7c1a) so
        # they propagate correctly across all partitions in PG 14+.
        {"postgresql_partition_by": "RANGE (recorded_at)"},
    )

    # ── Primary key (composite for partitioned table) ────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, primary_key=True
    )

    # ── Core telemetry fields ────────────────────────────────────────────────
    fleet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    speed: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    battery_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # ── v2 enrichment fields ─────────────────────────────────────────────────
    acceleration: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 3), nullable=True)
    weather: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    engine_on: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # ── v3: JSONB scenarios column ───────────────────────────────────────────
    # Stores detected scenario tags, e.g. ["hard_brake", "risky_weather_event"].
    # JSONB chosen over TEXT[] for native @> containment and richer future queries.
    scenarios: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
