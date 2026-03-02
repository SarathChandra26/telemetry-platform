"""initial schema

Revision ID: 5a1f9b6ffed5
Revises:
Create Date: 2026-02-26 00:00:00.000000

"""
from __future__ import annotations
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "5a1f9b6ffed5"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # fleets
    # ------------------------------------------------------------------
    op.create_table(
        "fleets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("api_key_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("api_key_hash"),
    )

    # ------------------------------------------------------------------
    # vehicles
    # ------------------------------------------------------------------
    op.create_table(
        "vehicles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fleet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vin", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["fleet_id"], ["fleets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fleet_id", "vin"),
    )
    op.create_index("idx_vehicles_fleet_id", "vehicles", ["fleet_id"])

    # ------------------------------------------------------------------
    # telemetry_events  — partitioned by recorded_at (RANGE, monthly)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE telemetry_events (
            id              UUID            NOT NULL,
            fleet_id        UUID            NOT NULL,
            vehicle_id      UUID            NOT NULL,
            speed           NUMERIC(6, 2)   NOT NULL,
            latitude        NUMERIC(9, 6)   NOT NULL,
            longitude       NUMERIC(9, 6)   NOT NULL,
            battery_level   SMALLINT        NOT NULL,
            recorded_at     TIMESTAMPTZ     NOT NULL,
            ingested_at     TIMESTAMPTZ     NOT NULL DEFAULT now(),
            PRIMARY KEY (id, recorded_at),
            CONSTRAINT ck_speed_range    CHECK (speed >= 0 AND speed <= 500),
            CONSTRAINT ck_lat_range      CHECK (latitude >= -90 AND latitude <= 90),
            CONSTRAINT ck_lon_range      CHECK (longitude >= -180 AND longitude <= 180),
            CONSTRAINT ck_battery_range  CHECK (battery_level >= 0 AND battery_level <= 100)
        ) PARTITION BY RANGE (recorded_at);
    """)

    op.create_index(
        "idx_telemetry_fleet_recorded",
        "telemetry_events",
        ["fleet_id", "recorded_at"],
    )
    op.create_index(
        "idx_telemetry_vehicle_recorded",
        "telemetry_events",
        ["vehicle_id", "recorded_at"],
    )

    # ------------------------------------------------------------------
    # Create monthly partitions: 1 month back through 3 months ahead
    # This covers historical back-fills, current month, and near future.
    # ------------------------------------------------------------------
    now = datetime.now(tz=timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    for i in range(-1, 4):   # -1 month back, then 0 through +3
        start = now + relativedelta(months=i)
        end   = start + relativedelta(months=1)
        name  = f"telemetry_events_{start.strftime('%Y_%m')}"
        op.execute(f"""
            CREATE TABLE IF NOT EXISTS {name}
                PARTITION OF telemetry_events
                FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}');
        """)

    # ------------------------------------------------------------------
    # hourly_aggregates
    # ------------------------------------------------------------------
    op.create_table(
        "hourly_aggregates",
        sa.Column("fleet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hour_bucket", sa.DateTime(timezone=True), nullable=False),
        sa.Column("avg_speed", sa.Numeric(6, 2), nullable=True),
        sa.Column("max_speed", sa.Numeric(6, 2), nullable=True),
        sa.Column("min_battery", sa.SmallInteger(), nullable=True),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("fleet_id", "vehicle_id", "hour_bucket"),
    )
    op.create_index(
        "idx_hourly_fleet_hour", "hourly_aggregates", ["fleet_id", "hour_bucket"]
    )


def downgrade() -> None:
    op.drop_table("hourly_aggregates")
    op.execute("DROP TABLE IF EXISTS telemetry_events CASCADE;")
    op.drop_table("vehicles")
    op.drop_table("fleets")