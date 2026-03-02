from __future__ import annotations
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.core.exceptions import RateLimitExceededError
from app.dependencies import get_db_session, get_redis, get_telemetry_service
from app.schemas.telemetry import TelemetryIngestRequest, TelemetryIngestResponse
from app.services.telemetry import TelemetryService

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
logger = structlog.get_logger(__name__)


def _build_service(
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> TelemetryService:
    return get_telemetry_service(session, redis)


@router.post(
    "",
    response_model=TelemetryIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a telemetry event",
)
async def ingest_telemetry(
    payload: TelemetryIngestRequest,
    service: Annotated[TelemetryService, Depends(_build_service)],
) -> TelemetryIngestResponse:
    try:
        return await service.ingest(payload)
    except RateLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for fleet {exc.fleet_id}",
            headers={"Retry-After": "60"},
        )
