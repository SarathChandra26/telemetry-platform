"""tests/integration/test_scenario_analytics.py

Integration tests for the v3 scenario analytics endpoints:
  GET /api/v1/analytics/fleet/{fleet_id}/scenarios
  GET /api/v1/analytics/fleet/{fleet_id}/scenario-summary

Uses the shared httpx AsyncClient + mock Redis fixtures from conftest.py.
The DB is the in-memory test Postgres (or SQLite for CI), so these tests
verify HTTP contract, caching behaviour, and 422 validation — not real data.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest


# ---------------------------------------------------------------------------
# GET /analytics/fleet/{fleet_id}/scenarios
# ---------------------------------------------------------------------------

class TestFleetScenarioEvents:
    @pytest.mark.asyncio
    async def test_returns_200_on_cache_miss(self, client, mock_redis) -> None:
        fleet_id = uuid.uuid4()
        mock_redis.get.return_value = None  # cache miss → hits DB (empty in test)

        response = await client.get(
            f"/api/v1/analytics/fleet/{fleet_id}/scenarios",
            params={"scenario": "hard_brake"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_response_schema_on_cache_miss(self, client, mock_redis) -> None:
        fleet_id = uuid.uuid4()
        mock_redis.get.return_value = None

        response = await client.get(
            f"/api/v1/analytics/fleet/{fleet_id}/scenarios",
            params={"scenario": "low_battery"},
        )
        body = response.json()
        assert "fleet_id" in body
        assert "scenario" in body
        assert "total" in body
        assert "results" in body
        assert isinstance(body["results"], list)

    @pytest.mark.asyncio
    async def test_returns_200_on_cache_hit(self, client, mock_redis) -> None:
        fleet_id = uuid.uuid4()
        cached_payload = {
            "fleet_id": str(fleet_id),
            "scenario": "over_speeding",
            "total": 7,
            "limit": 100,
            "offset": 0,
            "results": [],
        }
        mock_redis.get.return_value = json.dumps(cached_payload)

        response = await client.get(
            f"/api/v1/analytics/fleet/{fleet_id}/scenarios",
            params={"scenario": "over_speeding"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 7
        assert body["scenario"] == "over_speeding"

    @pytest.mark.asyncio
    async def test_unknown_scenario_returns_422(self, client) -> None:
        fleet_id = uuid.uuid4()
        response = await client.get(
            f"/api/v1/analytics/fleet/{fleet_id}/scenarios",
            params={"scenario": "not_a_real_scenario"},
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "valid_values" in detail

    @pytest.mark.asyncio
    async def test_missing_scenario_param_returns_422(self, client) -> None:
        """scenario is a required query param."""
        fleet_id = uuid.uuid4()
        response = await client.get(
            f"/api/v1/analytics/fleet/{fleet_id}/scenarios"
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_limit_returns_422(self, client) -> None:
        fleet_id = uuid.uuid4()
        response = await client.get(
            f"/api/v1/analytics/fleet/{fleet_id}/scenarios",
            params={"scenario": "hard_brake", "limit": 9999},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "scenario",
        ["hard_brake", "rapid_acceleration", "over_speeding", "low_battery", "risky_weather_event"],
    )
    async def test_all_valid_scenario_labels_accepted(
        self, client, mock_redis, scenario: str
    ) -> None:
        fleet_id = uuid.uuid4()
        mock_redis.get.return_value = None

        response = await client.get(
            f"/api/v1/analytics/fleet/{fleet_id}/scenarios",
            params={"scenario": scenario},
        )
        assert response.status_code == 200, f"Unexpected 422 for scenario='{scenario}'"


# ---------------------------------------------------------------------------
# GET /analytics/fleet/{fleet_id}/scenario-summary
# ---------------------------------------------------------------------------

class TestFleetScenarioSummary:
    @pytest.mark.asyncio
    async def test_returns_200_on_cache_miss(self, client, mock_redis) -> None:
        fleet_id = uuid.uuid4()
        mock_redis.get.return_value = None

        response = await client.get(
            f"/api/v1/analytics/fleet/{fleet_id}/scenario-summary"
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_response_schema_contains_summary_dict(
        self, client, mock_redis
    ) -> None:
        fleet_id = uuid.uuid4()
        mock_redis.get.return_value = None

        response = await client.get(
            f"/api/v1/analytics/fleet/{fleet_id}/scenario-summary"
        )
        body = response.json()
        assert "fleet_id" in body
        assert "summary" in body
        assert isinstance(body["summary"], dict)

    @pytest.mark.asyncio
    async def test_returns_200_on_cache_hit(self, client, mock_redis) -> None:
        fleet_id = uuid.uuid4()
        cached_payload = {
            "fleet_id": str(fleet_id),
            "from_date": None,
            "to_date": None,
            "summary": {
                "hard_brake": 23,
                "over_speeding": 15,
                "low_battery": 5,
            },
        }
        mock_redis.get.return_value = json.dumps(cached_payload)

        response = await client.get(
            f"/api/v1/analytics/fleet/{fleet_id}/scenario-summary"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["summary"]["hard_brake"] == 23
        assert body["summary"]["over_speeding"] == 15
        assert body["summary"]["low_battery"] == 5

    @pytest.mark.asyncio
    async def test_accepts_time_range_params(self, client, mock_redis) -> None:
        fleet_id = uuid.uuid4()
        mock_redis.get.return_value = None

        response = await client.get(
            f"/api/v1/analytics/fleet/{fleet_id}/scenario-summary",
            params={
                "from_date": "2026-01-01T00:00:00Z",
                "to_date": "2026-02-01T00:00:00Z",
            },
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_empty_summary_for_fleet_with_no_events(
        self, client, mock_redis
    ) -> None:
        """A fleet with zero enriched events should return an empty summary dict."""
        fleet_id = uuid.uuid4()
        mock_redis.get.return_value = None

        response = await client.get(
            f"/api/v1/analytics/fleet/{fleet_id}/scenario-summary"
        )
        assert response.status_code == 200
        body = response.json()
        # Test DB has no data → summary should be an empty dict (not an error)
        assert body["summary"] == {}
