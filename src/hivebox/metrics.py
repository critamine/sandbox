import time
from fastapi import APIRouter, Response
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

REQUESTS = Counter(
    "hivebox_requests_total",
    "Total HTTP requests",
    ["endpoint", "method", "result"]
)

REQUEST_LATENCY = Histogram(
    "hivebox_http_latency_milliseconds",
    "HTTP request latency in milliseconds",
    ["endpoint", "method"]
)

OPENSENSEMAP_CALLS = Counter(
    "hivebox_opensensemap_calls_total",
    "External API calls to openSenseMap",
    ["mode", "sensebox_id", "result"]
)

OPENSENSEMAP_LATENCY = Histogram(
    "hivebox_opensensemap_latency_seconds",
    "Latency of openSenseMap API calls in seconds",
    ["sensebox_id"]
)

S3_CALLS = Counter(
    "hivebox_s3_calls_total",
    "Number of store operations to S3",
    ["mode", "operation", "result"]
)

READYZ_CHECKS = Counter(
    "hivebox_readyz_checks_total",
    "Total /readyz checks",
    ["reason", "result"]
)

REDIS_CALLS = Counter(
    "hivebox_redis_calls_total",
    "Number of Redis operations",
    ["mode", "operation", "result"]
)

CACHED_TEMPERATURE = Gauge(
    "hivebox_cached_temperature_celsius",
    "Last temperature cached to redis",
)

CACHE_TIMESTAMP = Gauge(
    "hivebox_cache_timestamp_seconds",
    "Timestamp of the temperature data in the cache in seconds (UTC)",
)

CACHE_AGE = Gauge(
    "hivebox_cache_age_seconds",
    "Age of the temperature data in the cache in seconds",
)

router = APIRouter()

@router.get("/metrics")
def metrics() -> Response:
    """Expose Prometheus metrics, calculating cache age on the fly."""
    last_timestamp = CACHE_TIMESTAMP._value.get()

    if last_timestamp > 0:
        current_time = time.time()
        age = current_time - last_timestamp
        CACHE_AGE.set(age)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)