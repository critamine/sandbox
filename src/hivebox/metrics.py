import time
from fastapi import APIRouter, Response, status
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from . import SENSEBOX_TEMP_SENSORS

REQUESTS = Counter(
    "hivebox_requests_total",
    "Total HTTP requests",
    ["endpoint", "method", "result"]
)

REQUEST_LATENCY = Histogram(
    "hivebox_http_latency_seconds",
    "Latency of HTTP requests",
    ["endpoint", "method"]
)

OPENSENSEMAP_CALLS = Counter(
    "hivebox_opensensemap_calls_total",
    "External API calls to openSenseMap",
    ["mode", "sensebox_id", "result"]
)

OPENSENSEMAP_LATENCY = Histogram(
    "hivebox_opensensemap_latency_seconds",
    "Latency of openSenseMap API calls",
    ["sensebox_id"]
)

AGE_BUCKETS = (60, 120, 180, 240, 300)

OPENSENSEMAP_AGE = Histogram(
    "hivebox_opensensemap_reading_age_seconds",
    "Age of openSenseMap readings in seconds",
    ["sensebox_id"],
    buckets=AGE_BUCKETS
)

S3_CALLS = Counter(
    "hivebox_s3_calls_total",
    "Number of store operations to S3",
    ["mode", "operation", "result"]
)

S3_LATENCY = Histogram(
    "hivebox_s3_latency_seconds",
    "Latency of S3 operations",
    ["operation", "result"]
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

REDIS_LATENCY = Histogram(
    "hivebox_redis_latency_seconds",
    "Latency of redis operations",
    ["operation", "result"]
)

DEPENDENCY_RECONNECT_THROTTLED = Counter(
    "hivebox_dependency_reconnect_throttled_total",
    "Total times a dependency reconnect was throttled due to back-off",
    ["dependency"]
)

CACHED_TEMPERATURE = Gauge(
    "hivebox_cached_temperature_celsius",
    "Value of last cached temperature",
)

CACHE_TIMESTAMP = Gauge(
    "hivebox_cache_timestamp_seconds",
    "Timestamp of the temperature data in the cache in seconds (UTC)",
)

CACHE_AGE = Gauge(
    "hivebox_cache_age_seconds",
    "Age of the temperature data in the cache in seconds",
)

TEMPERATURE_SENSORS_USED = Gauge(
    "hivebox_temperature_sensors_used_gauge",
    "Number of sensors used in the last successful temperature calculation",
)

UNREACHABLE_SENSORS = Gauge(
    "hivebox_unreachable_sensors_total",
    "Total number of unreachable sensors in the last poll",
)

POLL_JOB_DURATION = Histogram(
    "hivebox_poll_job_duration_seconds",
    "Duration of the poll job in seconds",
    ["result"]
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

@router.get("/readyz")
def readyz(response: Response):
    """
    Readiness probe. Returns 200 OK if the service is ready.

    Returns 503 Service Unavailable if:
    1. More than 50% of sensors are unreachable, AND
    2. The cache is older than 5 minutes.
    """
    total_sensors = len(SENSEBOX_TEMP_SENSORS)
    failure_threshold = (total_sensors // 2) + 1

    unreachable_count = UNREACHABLE_SENSORS._value.get()
    last_timestamp = CACHE_TIMESTAMP._value.get()
    cache_age = time.time() - last_timestamp if last_timestamp > 0 else float('inf')

    is_unhealthy = (unreachable_count >= failure_threshold and cache_age > 300)

    if is_unhealthy:
        reason = "quorum_lost_and_cache_stale"
        READYZ_CHECKS.labels(reason=reason, result="fail").inc()
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unready", "reason": reason}

    READYZ_CHECKS.labels(reason="ok", result="success").inc()
    return {"status": "ready"}