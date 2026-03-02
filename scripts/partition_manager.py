#!/usr/bin/env python3
"""
Ensures monthly partitions exist for the next N months.
Idempotent — safe to run repeatedly.

Usage:
    python scripts/partition_manager.py --months-ahead 3

Run as a monthly CronJob in production.
Also called automatically at application startup.
"""
from __future__ import annotations
import argparse
import asyncio
import os
from datetime import datetime, timezone

import asyncpg
from dateutil.relativedelta import relativedelta


async def ensure_partitions(dsn: str, months_ahead: int = 3, months_back: int = 1) -> None:
    """
    Create monthly child partitions for telemetry_events.

    Creates partitions from `months_back` months ago through `months_ahead`
    months into the future. Idempotent — existing partitions are skipped.

    Args:
        dsn:          asyncpg-compatible DSN string.
        months_ahead: How many future months to pre-create (default 3).
        months_back:  How many past months to ensure exist (default 1).
    """
    conn = await asyncpg.connect(dsn)
    now = datetime.now(tz=timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    for i in range(-months_back, months_ahead + 1):
        start = now + relativedelta(months=i)
        end = start + relativedelta(months=1)
        partition_name = f"telemetry_events_{start.strftime('%Y_%m')}"

        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_tables WHERE tablename = $1)",
            partition_name,
        )

        if exists:
            print(f"  Partition {partition_name} already exists — skipping.")
            continue

        sql = f"""
            CREATE TABLE IF NOT EXISTS {partition_name}
                PARTITION OF telemetry_events
                FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}');
        """
        await conn.execute(sql)
        print(f"  Created partition: {partition_name} [{start.date()} -> {end.date()})")

    await conn.close()
    print("Partition management complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dsn",
        default=os.environ.get(
            "DATABASE_URL",
            "postgresql://telemetry:secret@localhost:5432/telemetry",
        ).replace("postgresql+asyncpg://", "postgresql://"),
    )
    parser.add_argument("--months-ahead", type=int, default=3)
    parser.add_argument("--months-back", type=int, default=1)
    args = parser.parse_args()
    asyncio.run(ensure_partitions(args.dsn, args.months_ahead, args.months_back))