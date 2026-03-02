from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

REGISTRY = CollectorRegistry(auto_describe=True)

ingestion_total = Counter(
    "telemetry_ingestion_total",
    "Total number of telemetry events ingested",
    ["fleet_id", "status"],
    registry=REGISTRY,
)

ingestion_latency = Histogram(
    "telemetry_ingestion_latency_seconds",
    "Ingestion endpoint latency in seconds",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
    registry=REGISTRY,
)

cache_hits = Counter(
    "telemetry_cache_hits_total",
    "Number of Redis cache hits on analytics endpoints",
    ["endpoint"],
    registry=REGISTRY,
)

cache_misses = Counter(
    "telemetry_cache_misses_total",
    "Number of Redis cache misses on analytics endpoints",
    ["endpoint"],
    registry=REGISTRY,
)

worker_job_duration = Histogram(
    "telemetry_worker_job_duration_seconds",
    "Background worker job duration",
    ["task_name"],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0],
    registry=REGISTRY,
)

active_db_connections = Gauge(
    "telemetry_db_active_connections",
    "Number of active database pool connections",
    registry=REGISTRY,
)

rate_limit_rejections = Counter(
    "telemetry_rate_limit_rejections_total",
    "Number of requests rejected by rate limiter",
    ["fleet_id"],
    registry=REGISTRY,
)
