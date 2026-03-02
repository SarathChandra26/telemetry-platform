from __future__ import annotations
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from pathlib import Path

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from redis.asyncio import ConnectionPool

from app.api.v1.router import api_v1_router
from app.config import settings
from app.dependencies import set_redis_pool
from app.db.engine import primary_engine, replica_engine
from app.observability.logging import configure_logging
from app.observability.metrics import REGISTRY

logger = structlog.get_logger(__name__)

# -------------------------------------------------
# Template & Static Configuration
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(BASE_DIR / "web/templates"))


# -------------------------------------------------
# Partition Management
# -------------------------------------------------

async def _ensure_partitions() -> None:
    """Create missing monthly partitions at startup. Idempotent."""
    try:
        from scripts.partition_manager import ensure_partitions
        dsn = str(settings.database_url).replace("postgresql+asyncpg://", "postgresql://")
        await ensure_partitions(dsn, months_ahead=3, months_back=1)
    except Exception as exc:
        logger.warning("partition_management_failed", error=str(exc))


# -------------------------------------------------
# Lifespan
# -------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    logger.info("startup_begin", environment=settings.environment)

    pool = ConnectionPool.from_url(
        str(settings.redis_url),
        max_connections=settings.redis_max_connections,
        decode_responses=True,
    )
    set_redis_pool(pool)

    await _ensure_partitions()

    logger.info("startup_complete")
    yield

    logger.info("shutdown_begin")
    await pool.aclose()
    await primary_engine.dispose()
    await replica_engine.dispose()
    logger.info("shutdown_complete")


# -------------------------------------------------
# App Factory
# -------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="Telemetry Data Processing Platform",
        version="1.0.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Mount static files
    app.mount(
        "/static",
        StaticFiles(directory=str(BASE_DIR / "web/static")),
        name="static",
    )

    # -------------------------------------------------
    # Middleware
    # -------------------------------------------------

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        import uuid
        import structlog.contextvars

        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # -------------------------------------------------
    # Global Exception Handler
    # -------------------------------------------------

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    # -------------------------------------------------
    # API Router
    # -------------------------------------------------

    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    # -------------------------------------------------
    # Web Dashboard Routes
    # -------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "fleet_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            },
        )

    @app.get("/telemetry-ui", response_class=HTMLResponse)
    async def telemetry_form(request: Request):
        return templates.TemplateResponse(
            "telemetry_form.html",
            {"request": request},
        )

    # -------------------------------------------------
    # Health & Metrics
    # -------------------------------------------------

    @app.get("/health", include_in_schema=False)
    async def health() -> dict:
        return {"status": "ok", "environment": settings.environment}

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(
            content=generate_latest(REGISTRY),
            media_type=CONTENT_TYPE_LATEST,
        )

    return app


app = create_app()