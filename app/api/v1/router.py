from fastapi import APIRouter
from app.api.v1 import telemetry, analytics

api_v1_router = APIRouter()
api_v1_router.include_router(telemetry.router)
api_v1_router.include_router(analytics.router)
