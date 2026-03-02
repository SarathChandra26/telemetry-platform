from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import UUID, Numeric, SmallInteger, Integer, DateTime, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HourlyAggregate(Base):
    __tablename__ = "hourly_aggregates"
    __table_args__ = (
        Index("idx_hourly_fleet_hour", "fleet_id", "hour_bucket"),
    )

    fleet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    hour_bucket: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    avg_speed: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    max_speed: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    min_battery: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
