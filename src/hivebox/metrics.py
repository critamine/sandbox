from fastapi import APIRouter, Response
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

REQUESTS = Counter(
    "hivebox_requests_total",
    "Total HTTP requests",
    ["endpoint", "method", "result"]
)

OPENSENSEMAP_CALLS = Counter(
    "hivebox_opensensemap_calls_total",
    "External API calls to openSenseMap",
    ["mode", "sensebox_id", "result"]
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

router = APIRouter()

@router.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)