#!/usr/bin/env python3
"""
Benchmark the ingestion endpoint with configurable concurrency.

Usage:
    python scripts/benchmark_ingestion.py --url http://localhost:8000 \
        --requests 10000 --concurrency 100
"""
from __future__ import annotations
import argparse
import asyncio
import time
import uuid
from datetime import datetime, timezone
from statistics import mean, quantiles

import httpx


def make_payload(fleet_id: str) -> dict:
    return {
        "fleet_id": fleet_id,
        "vehicle_id": str(uuid.uuid4()),
        "speed": "95.50",
        "latitude": "35.676200",
        "longitude": "139.650300",
        "battery_level": 72,
        "recorded_at": datetime.now(tz=timezone.utc).isoformat(),
    }


async def send_request(
    client: httpx.AsyncClient,
    url: str,
    fleet_id: str,
    latencies: list[float],
    errors: list[int],
) -> None:
    start = time.perf_counter()
    try:
        response = await client.post(
            f"{url}/api/v1/telemetry",
            json=make_payload(fleet_id),
            timeout=10.0,
        )
        latencies.append(time.perf_counter() - start)
        if response.status_code not in (200, 201):
            errors.append(response.status_code)
    except Exception:
        latencies.append(time.perf_counter() - start)
        errors.append(-1)


async def benchmark(base_url: str, total_requests: int, concurrency: int) -> None:
    fleet_id = str(uuid.uuid4())
    latencies: list[float] = []
    errors: list[int] = []
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded(client):
        async with semaphore:
            await send_request(client, base_url, fleet_id, latencies, errors)

    limits = httpx.Limits(
        max_connections=concurrency, max_keepalive_connections=concurrency
    )
    async with httpx.AsyncClient(limits=limits) as client:
        start = time.perf_counter()
        await asyncio.gather(*[bounded(client) for _ in range(total_requests)])
        total_time = time.perf_counter() - start

    qs = quantiles(latencies, n=100)
    print(f"\n{'='*50}")
    print(f"  Total requests:  {total_requests}")
    print(f"  Concurrency:     {concurrency}")
    print(f"  Total time:      {total_time:.2f}s")
    print(f"  Throughput:      {total_requests / total_time:.0f} req/s")
    print(f"  Errors:          {len(errors)} ({len(errors)/total_requests*100:.1f}%)")
    print(f"  Latency p50:     {qs[49]*1000:.1f}ms")
    print(f"  Latency p95:     {qs[94]*1000:.1f}ms")
    print(f"  Latency p99:     {qs[98]*1000:.1f}ms")
    print(f"  Latency mean:    {mean(latencies)*1000:.1f}ms")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--requests", type=int, default=5000)
    parser.add_argument("--concurrency", type=int, default=50)
    args = parser.parse_args()
    asyncio.run(benchmark(args.url, args.requests, args.concurrency))
