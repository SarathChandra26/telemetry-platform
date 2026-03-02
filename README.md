# Telemetry Data Processing Platform

A production-grade distributed telemetry ingestion and analytics system built for fleet vehicle monitoring.

## Stack

- **FastAPI** (async) — ingestion & analytics API
- **PostgreSQL 16** — partitioned telemetry storage (RANGE by month)
- **Redis 7** — token bucket rate limiting, cache-aside, ARQ job queue
- **ARQ** — async background workers (aggregation, anomaly detection)
- **SQLAlchemy 2.x async** — ORM + raw SQL for analytics
- **Pydantic v2** — strict input validation
- **structlog** — structured JSON logging
- **Prometheus + Grafana** — metrics & dashboards
- **Docker** — multi-stage builds, non-root user

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

API docs: http://localhost:8000/docs  
Grafana: http://localhost:3000 (admin/admin)  
Prometheus: http://localhost:9090

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/telemetry` | Ingest a telemetry event |
| GET | `/api/v1/analytics/fleet/{id}/summary` | Fleet-wide summary |
| GET | `/api/v1/analytics/fleet/{id}/low-battery` | Low battery alerts |
| GET | `/api/v1/analytics/vehicle/{fleet_id}/{vehicle_id}/hourly` | Hourly speed stats |
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

## Seed Data

```bash
python scripts/seed_data.py --fleets 3 --vehicles 10 --events 5000
```

## Benchmark

```bash
python scripts/benchmark_ingestion.py --requests 10000 --concurrency 100
```

## Tests

```bash
pytest tests/ -v --cov=app
```

## Partition Management

```bash
python scripts/partition_manager.py --months-ahead 3
```

## Architecture

```
POST /telemetry → RateLimit (Redis) → Validate → INSERT (PostgreSQL) → Enqueue (ARQ)
GET  /analytics → Cache Check (Redis) → DB Query (Read Replica) → Cache Set → Response
ARQ Worker      → Aggregate hourly → UPSERT hourly_aggregates → Invalidate cache
```

## Key Design Decisions

- **Partitioning by `recorded_at`**: enables partition pruning on all time-range queries and clean archival
- **Denormalized `fleet_id`**: avoids JOIN on hot write path, tenant isolation enforced at service layer
- **Fail-open rate limiter**: Redis outage degrades to no rate limiting, not service outage
- **Idempotent workers**: `ON CONFLICT DO UPDATE` makes aggregation jobs safe to retry
- **Read replica routing**: all analytics queries use separate engine bound to replica
