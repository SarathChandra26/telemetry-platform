"""
Convert scenarios column from TEXT[] to JSONB, add GIN index.

Why JSONB over TEXT[]:
  - Native @> containment queries without casting
  - Richer future queries (nested metadata per scenario)
  - Better interoperability with analytics tooling
  - Better GIN optimization in PostgreSQL 14+

Revision ID: b5f83d2e7c1a
Revises: a3e72c9d1f04
Create Date: 2026-02-27 12:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "b5f83d2e7c1a"
down_revision = "a3e72c9d1f04"
branch_labels = None
depends_on = None


# ============================================================
# UPGRADE
# ============================================================

def upgrade() -> None:
    # ------------------------------------------------------------
    # 1. Drop old TEXT[] indexes (if they exist)
    # ------------------------------------------------------------
    op.execute("DROP INDEX IF EXISTS idx_telemetry_scenarios_gin")
    op.execute("DROP INDEX IF EXISTS idx_telemetry_fleet_scenarios")

    # ------------------------------------------------------------
    # 2. Drop existing TEXT[] default BEFORE type change
    #    (Postgres cannot auto-cast defaults during ALTER TYPE)
    # ------------------------------------------------------------
    op.execute("""
        ALTER TABLE telemetry_events
        ALTER COLUMN scenarios DROP DEFAULT
    """)

    # ------------------------------------------------------------
    # 3. Convert TEXT[] → JSONB
    # ------------------------------------------------------------
    op.execute("""
        ALTER TABLE telemetry_events
        ALTER COLUMN scenarios
        TYPE JSONB
        USING CASE
            WHEN scenarios IS NULL THEN '[]'::jsonb
            ELSE to_jsonb(scenarios)
        END
    """)

    # ------------------------------------------------------------
    # 4. Set new JSONB default
    # ------------------------------------------------------------
    op.execute("""
        ALTER TABLE telemetry_events
        ALTER COLUMN scenarios
        SET DEFAULT '[]'::jsonb
    """)

    # ------------------------------------------------------------
    # 5. Backfill any remaining NULLs
    # ------------------------------------------------------------
    op.execute("""
        UPDATE telemetry_events
        SET scenarios = '[]'::jsonb
        WHERE scenarios IS NULL
    """)

    # ------------------------------------------------------------
    # 6. Enforce NOT NULL
    # ------------------------------------------------------------
    op.execute("""
        ALTER TABLE telemetry_events
        ALTER COLUMN scenarios SET NOT NULL
    """)

    # ------------------------------------------------------------
    # 7. JSONB GIN index for containment queries (@>)
    # ------------------------------------------------------------
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_scenarios_gin
        ON telemetry_events
        USING GIN (scenarios jsonb_path_ops)
    """)

    # ------------------------------------------------------------
    # 8. Fleet + time optimized partial index
    # ------------------------------------------------------------
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_fleet_scenarios_time
        ON telemetry_events (fleet_id, recorded_at DESC)
        WHERE jsonb_array_length(scenarios) > 0
    """)


# ============================================================
# DOWNGRADE
# ============================================================

def downgrade() -> None:
    # Drop JSONB indexes
    op.execute("DROP INDEX IF EXISTS idx_telemetry_fleet_scenarios_time")
    op.execute("DROP INDEX IF EXISTS idx_telemetry_scenarios_gin")

    # Allow NULL before conversion
    op.execute("""
        ALTER TABLE telemetry_events
        ALTER COLUMN scenarios DROP NOT NULL
    """)

    # Drop JSONB default
    op.execute("""
        ALTER TABLE telemetry_events
        ALTER COLUMN scenarios DROP DEFAULT
    """)

    # Convert JSONB back to TEXT[]
    op.execute("""
        ALTER TABLE telemetry_events
        ALTER COLUMN scenarios
        TYPE TEXT[]
        USING ARRAY(
            SELECT jsonb_array_elements_text(scenarios)
        )
    """)

    # Restore TEXT[] default
    op.execute("""
        ALTER TABLE telemetry_events
        ALTER COLUMN scenarios
        SET DEFAULT '{}'::text[]
    """)

    # Restore old TEXT[] GIN index
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_scenarios_gin
        ON telemetry_events
        USING GIN (scenarios)
    """)