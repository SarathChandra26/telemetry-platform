from arq.connections import RedisSettings
from app.config import settings


async def startup(ctx: dict) -> None:
    import structlog
    from app.db.engine import AsyncSessionLocal
    from app.observability.logging import configure_logging

    configure_logging()
    ctx["session_factory"] = AsyncSessionLocal
    ctx["logger"] = structlog.get_logger("worker")


async def shutdown(ctx: dict) -> None:
    pass


class WorkerSettings:
    functions = [
        "app.workers.tasks.aggregation.aggregate_hourly",
        "app.workers.tasks.anomaly.detect_anomalies",
    ]
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 20
    job_timeout = 300
    keep_result = 3600
    retry_jobs = True
    max_tries = 3
    health_check_interval = 30
