"""add scenario enrichment columns

Adds acceleration, weather, engine_on, and scenarios (TEXT[]) to the
telemetry_events partitioned table, then creates a GIN index on the
scenarios array for fast containment queries (@>).

Since telemetry_events is PARTITION BY RANGE, DDL must be issued on the
parent; Postgres 14+ automatically propagates column additions to existing
partitions.  The GIN index is created on the parent with ON ONLY=false so
it propagates to every existing partition as well.

Revision ID: a3e72c9d1f04
Revises: 5a1f9b6ffed5
Create Date: 2026-02-27 00:00:00.000000
"""
from __future__ import annotations

from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ---------------------------------------------------------------------------
# Revision metadata
# ---------------------------------------------------------------------------
revision = "a3e72c9d1f04"
down_revision = "5a1f9b6ffed5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Add new enrichment columns to the partitioned parent table.
    #    Postgres propagates ADD COLUMN to all existing partitions.
    # ------------------------------------------------------------------
    op.add_column(
        "telemetry_events",
        sa.Column("acceleration", sa.Numeric(7, 3), nullable=True),
    )
    op.add_column(
        "telemetry_events",
        sa.Column("weather", sa.Text(), nullable=True),
    )
    op.add_column(
        "telemetry_events",
        sa.Column("engine_on", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "telemetry_events",
        sa.Column(
            "scenarios",
            postgresql.ARRAY(sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::text[]"),
        ),
    )

    # ------------------------------------------------------------------
    # 2. GIN index on the scenarios array.
    #
    #    Partitioned tables require that indexes be created on the parent;
    #    PG14+ propagates them to existing partitions automatically, and
    #    new partitions inherit the index template.
    #
    #    We use postgresql_using='gin' and postgresql_ops to target the
    #    array.  `op.create_index` cannot express GIN ops cleanly so we
    #    fall back to raw DDL which is cleaner and unambiguous.
    # ------------------------------------------------------------------
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_telemetry_scenarios_gin
    ON telemetry_events
    USING GIN (scenarios)
""")

    # ------------------------------------------------------------------
    # 3. Partial index to accelerate fleet + scenario compound queries.
    #    Filters to rows where scenarios is non-empty, keeping the index
    #    small on fleets that do not yet use enrichment.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_telemetry_fleet_scenarios
        ON telemetry_events (fleet_id, recorded_at DESC)
        WHERE scenarios IS NOT NULL AND array_length(scenarios, 1) > 0
        """
    )

    # ------------------------------------------------------------------
    # 4. Ensure any future monthly partitions are pre-created.
    #    The initial migration already built partitions up to now+3 months;
    #    we extend by one additional month to stay ahead of the window.
    # ------------------------------------------------------------------
    now = datetime.now(tz=timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    # +4 months out (initial migration only went to +3)
    for i in [4]:
        start = now + relativedelta(months=i)
        end   = start + relativedelta(months=1)
        name  = f"telemetry_events_{start.strftime('%Y_%m')}"
        op.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {name}
                PARTITION OF telemetry_events
                FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')
            """
        )


def downgrade() -> None:
    # Drop indexes first (CONCURRENTLY not supported inside transactions)
    op.execute("DROP INDEX IF EXISTS idx_telemetry_scenarios_gin")
    op.execute("DROP INDEX IF EXISTS idx_telemetry_fleet_scenarios")

    op.drop_column("telemetry_events", "scenarios")
    op.drop_column("telemetry_events", "engine_on")
    op.drop_column("telemetry_events", "weather")
    op.drop_column("telemetry_events", "acceleration")
