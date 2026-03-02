from __future__ import annotations
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

VALID_PAYLOAD = {
    "fleet_id": str(uuid.uuid4()),
    "vehicle_id": str(uuid.uuid4()),
    "speed": "87.50",
    "latitude": "35.676200",
    "longitude": "139.650300",
    "battery_level": 65,
    "recorded_at": datetime.now(tz=timezone.utc).isoformat(),
}


@pytest.mark.asyncio
async def test_ingest_returns_201(client):
    response = await client.post("/api/v1/telemetry", json=VALID_PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert "event_id" in body
    assert body["status"] == "accepted"


@pytest.mark.asyncio
async def test_ingest_invalid_speed_rejected(client):
    payload = {**VALID_PAYLOAD, "speed": "999"}
    response = await client.post("/api/v1/telemetry", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ingest_rate_limited(client, mock_redis):
    mock_redis.register_script.return_value = AsyncMock(return_value=0)
    response = await client.post("/api/v1/telemetry", json=VALID_PAYLOAD)
    assert response.status_code == 429
    assert "Retry-After" in response.headers


@pytest.mark.asyncio
async def test_ingest_timezone_naive_rejected(client):
    payload = {**VALID_PAYLOAD, "recorded_at": "2025-03-15T10:00:00"}
    response = await client.post("/api/v1/telemetry", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
