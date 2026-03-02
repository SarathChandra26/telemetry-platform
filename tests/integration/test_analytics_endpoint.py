from __future__ import annotations
import uuid
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_fleet_summary_cache_miss(client, mock_redis):
    fleet_id = uuid.uuid4()
    mock_redis.get.return_value = None  # cache miss

    response = await client.get(f"/api/v1/analytics/fleet/{fleet_id}/summary")
    # Will return empty summary from test DB — just assert it doesn't 500
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_fleet_summary_cache_hit(client, mock_redis):
    fleet_id = uuid.uuid4()
    cached_data = {
        "fleet_id": str(fleet_id),
        "total_vehicles": 5,
        "active_vehicles_last_hour": 3,
        "avg_speed_last_hour": "72.50",
        "low_battery_count": 1,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    mock_redis.get.return_value = json.dumps(cached_data)

    response = await client.get(f"/api/v1/analytics/fleet/{fleet_id}/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_vehicles"] == 5


@pytest.mark.asyncio
async def test_low_battery_invalid_threshold(client):
    fleet_id = uuid.uuid4()
    response = await client.get(
        f"/api/v1/analytics/fleet/{fleet_id}/low-battery?threshold=200"
    )
    assert response.status_code == 422
