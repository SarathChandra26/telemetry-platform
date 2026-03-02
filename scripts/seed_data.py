#!/usr/bin/env python3
"""
Seed synthetic telemetry data for development and benchmarking.

Usage:
    python scripts/seed_data.py --fleets 5 --vehicles 20 --events 10000
"""
from __future__ import annotations
import argparse
import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg


async def seed(
    dsn: str,
    num_fleets: int,
    vehicles_per_fleet: int,
    events_per_vehicle: int,
) -> None:
    conn = await asyncpg.connect(dsn)

    fleet_ids = [uuid.uuid4() for _ in range(num_fleets)]
    vehicle_ids = {
        fid: [uuid.uuid4() for _ in range(vehicles_per_fleet)]
        for fid in fleet_ids
    }

    await conn.executemany(
        "INSERT INTO fleets (id, name, api_key_hash) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
        [(fid, f"Fleet {i}", f"hash_{i}") for i, fid in enumerate(fleet_ids)],
    )

    vehicle_rows = []
    for fid, vids in vehicle_ids.items():
        for j, vid in enumerate(vids):
            vehicle_rows.append((vid, fid, f"VIN-{vid.hex[:8].upper()}"))
    await conn.executemany(
        "INSERT INTO vehicles (id, fleet_id, vin) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
        vehicle_rows,
    )

    now = datetime.now(tz=timezone.utc)
    batch_size = 500
    total_events = 0

    for fid, vids in vehicle_ids.items():
        for vid in vids:
            batch = []
            for k in range(events_per_vehicle):
                recorded_at = now - timedelta(seconds=k * 10)
                batch.append((
                    uuid.uuid4(),
                    fid,
                    vid,
                    round(random.uniform(0, 180), 2),
                    round(random.uniform(34.0, 36.0), 6),
                    round(random.uniform(135.0, 140.0), 6),
                    random.randint(5, 100),
                    recorded_at,
                ))
                if len(batch) >= batch_size:
                    await conn.executemany(
                        """INSERT INTO telemetry_events
                           (id, fleet_id, vehicle_id, speed, latitude, longitude,
                            battery_level, recorded_at)
                           VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
                        batch,
                    )
                    total_events += len(batch)
                    batch.clear()
                    print(f"\r  Inserted {total_events} events...", end="", flush=True)

            if batch:
                await conn.executemany(
                    """INSERT INTO telemetry_events
                       (id, fleet_id, vehicle_id, speed, latitude, longitude,
                        battery_level, recorded_at)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
                    batch,
                )
                total_events += len(batch)

    await conn.close()
    print(f"\nSeeded {total_events} events across {num_fleets} fleets.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dsn", default="postgresql://telemetry:secret@localhost:5432/telemetry"
    )
    parser.add_argument("--fleets", type=int, default=3)
    parser.add_argument("--vehicles", type=int, default=10)
    parser.add_argument("--events", type=int, default=5000)
    args = parser.parse_args()

    asyncio.run(seed(args.dsn, args.fleets, args.vehicles, args.events))
