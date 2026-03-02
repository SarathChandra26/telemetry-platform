"""tests/unit/test_telemetry_service.py

Unit tests for TelemetryService.ingest().

v3 update: mocks insert_event_with_scenarios instead of insert_event,
and patches app.services.telemetry.create_pool (unchanged location).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import RateLimitExceededError
from app.repositories.telemetry import TelemetryRepository
from app.schemas.telemetry import TelemetryIngestRequest
from app.services.telemetry import TelemetryService


def make_payload(**overrides) -> TelemetryIngestRequest:
    defaults = {
        "fleet_id": uuid.uuid4(),
        "vehicle_id": uuid.uuid4(),
        "speed": Decimal("85.50"),
        "latitude": Decimal("35.6762"),
        "longitude": Decimal("139.6503"),
        "battery_level": 72,
        "recorded_at": datetime.now(tz=timezone.utc),
    }
    return TelemetryIngestRequest(**{**defaults, **overrides})


def make_payload_with_scenarios(**overrides) -> TelemetryIngestRequest:
    """Payload that will trigger hard_brake and risky_weather_event."""
    return make_payload(
        acceleration=Decimal("-8.0"),
        weather="rain",
        **overrides,
    )


@pytest.mark.asyncio
async def test_ingest_success_returns_event_id() -> None:
    mock_repo = AsyncMock(spec=TelemetryRepository)
    expected_id = uuid.uuid4()
    mock_repo.insert_event_with_scenarios.return_value = expected_id

    mock_rate_limiter = AsyncMock()
    mock_rate_limiter.is_allowed.return_value = True

    service = TelemetryService(repository=mock_repo, rate_limiter=mock_rate_limiter)
    payload = make_payload()

    with patch("app.services.telemetry.create_pool") as mock_pool_factory:
        mock_pool = AsyncMock()
        mock_pool_factory.return_value = mock_pool
        response = await service.ingest(payload)

    assert response.event_id == expected_id
    assert response.status == "accepted"
    mock_rate_limiter.is_allowed.assert_awaited_once_with(str(payload.fleet_id))


@pytest.mark.asyncio
async def test_ingest_attaches_detected_scenarios() -> None:
    """Scenarios detected by domain engine are passed to the repository."""
    mock_repo = AsyncMock(spec=TelemetryRepository)
    mock_repo.insert_event_with_scenarios.return_value = uuid.uuid4()

    mock_rate_limiter = AsyncMock()
    mock_rate_limiter.is_allowed.return_value = True

    service = TelemetryService(repository=mock_repo, rate_limiter=mock_rate_limiter)
    # acceleration=-8 → hard_brake + risky_weather_event (weather=rain)
    payload = make_payload_with_scenarios()

    with patch("app.services.telemetry.create_pool") as mock_pool_factory:
        mock_pool_factory.return_value = AsyncMock()
        response = await service.ingest(payload)

    # Verify scenarios were passed to the repo
    call_kwargs = mock_repo.insert_event_with_scenarios.call_args
    scenarios_written: list[str] = call_kwargs.kwargs["scenarios"]
    assert "hard_brake" in scenarios_written
    assert "risky_weather_event" in scenarios_written

    # Response should also surface the detected scenarios
    assert "hard_brake" in response.scenarios
    assert "risky_weather_event" in response.scenarios


@pytest.mark.asyncio
async def test_ingest_rate_limited_raises_error() -> None:
    mock_repo = AsyncMock(spec=TelemetryRepository)
    mock_rate_limiter = AsyncMock()
    mock_rate_limiter.is_allowed.return_value = False

    service = TelemetryService(repository=mock_repo, rate_limiter=mock_rate_limiter)
    payload = make_payload()

    with pytest.raises(RateLimitExceededError) as exc_info:
        await service.ingest(payload)

    assert exc_info.value.fleet_id == payload.fleet_id
    mock_repo.insert_event_with_scenarios.assert_not_awaited()


@pytest.mark.asyncio
async def test_ingest_continues_if_queue_fails() -> None:
    """Redis job queue failure must never fail the ingestion response."""
    mock_repo = AsyncMock(spec=TelemetryRepository)
    mock_repo.insert_event_with_scenarios.return_value = uuid.uuid4()

    mock_rate_limiter = AsyncMock()
    mock_rate_limiter.is_allowed.return_value = True

    service = TelemetryService(repository=mock_repo, rate_limiter=mock_rate_limiter)
    payload = make_payload()

    with patch("app.services.telemetry.create_pool", side_effect=ConnectionError("Redis down")):
        response = await service.ingest(payload)

    assert response.status == "accepted"
    mock_repo.insert_event_with_scenarios.assert_awaited_once()


@pytest.mark.asyncio
async def test_ingest_no_scenarios_for_normal_event() -> None:
    """Normal driving payload produces an empty scenarios list."""
    mock_repo = AsyncMock(spec=TelemetryRepository)
    mock_repo.insert_event_with_scenarios.return_value = uuid.uuid4()

    mock_rate_limiter = AsyncMock()
    mock_rate_limiter.is_allowed.return_value = True

    service = TelemetryService(repository=mock_repo, rate_limiter=mock_rate_limiter)
    # Normal payload: no enrichment fields → no scenarios
    payload = make_payload()

    with patch("app.services.telemetry.create_pool") as mock_pool_factory:
        mock_pool_factory.return_value = AsyncMock()
        response = await service.ingest(payload)

    assert response.scenarios == []
    call_kwargs = mock_repo.insert_event_with_scenarios.call_args
    assert call_kwargs.kwargs["scenarios"] == []
