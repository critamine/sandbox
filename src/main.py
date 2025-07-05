"""Main entry point for the application."""

import logging
import sys
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI, Request, Response, HTTPException, Depends
from hivebox.config import get_settings, Settings
from hivebox.cache import CacheService, CacheServiceError
from hivebox.store import StorageService, StorageServiceError
from hivebox import __version__
from hivebox.temperature import (
    TemperatureService,
    TemperatureServiceError,
    TemperatureResult,
)
from hivebox.metrics import (
    router as metrics_router,
    REQUESTS,
    REQUEST_LATENCY,
    CACHED_TEMPERATURE,
    CACHE_TIMESTAMP,
    POLL_JOB_DURATION,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

sched = AsyncIOScheduler()

async def poll(job_id: str):
    """Periodically fetches and stores temperature data."""
    start_time = time.time()
    mode = "auto"
    next_delay = 300
    result = "success"
    tmp_sensors = get_settings().tmp_sensors
    osm_base_url = get_settings().osm_base_url
    s3_available = True
    
    try:
        last_temp, age = (None, None)
        try:
            last_temp, age = await app.state.store_svc.get_stored_temperature(mode)
        except StorageServiceError as e:
            s3_available = False
            logger.info("S3 data not available, proceeding to poll for new data: %s", e)

        if last_temp and age < 300:
            next_delay = 300 - age
            logger.info("S3 data is fresh. Hydrating cache. Next poll in %s seconds.", next_delay)
            await safe_cache_update(app.state.cache_svc, last_temp, mode)
        else:
            if last_temp:
                logger.info("S3 data is stale. Polling for new temperature data...")
            else:
                logger.info("Polling for new temperature data...")
            temp_svc = TemperatureService(osm_base_url, tmp_sensors)
            new_temp = temp_svc.get_average_temperature(mode)
            if s3_available:
                await app.state.store_svc.store_temperature_result(new_temp, mode)
            else:
                logger.warning(
                    "Skipping S3 store operation due to earlier connection failure."
                )
            await safe_cache_update(app.state.cache_svc, new_temp, mode)
            logger.info("Polled and updated stores. Next poll in %s seconds.", next_delay)
    except (TemperatureServiceError, StorageServiceError) as e:
        result = "error"
        logger.error("Polling job '%s' failed during data fetch/store: %s", job_id, e, exc_info=True)
    finally:
        duration = time.time() - start_time
        POLL_JOB_DURATION.labels(result=result).observe(duration)
        sched.reschedule_job(job_id, trigger=IntervalTrigger(seconds=next_delay))

job = sched.add_job(
    poll,
    IntervalTrigger(seconds=10),
    args=[ "dynamic_poll" ],
    id="dynamic_poll",
)

async def safe_cache_update(cache_svc, result: TemperatureResult, mode: str):
    try:
        await cache_svc.update(result, mode)
        CACHED_TEMPERATURE.set(result.value)
        CACHE_TIMESTAMP.set(result.timestamp)
    except Exception as e:
        print(f"Cache update error: {e}", flush=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    s3_config = settings.s3_config.model_dump(mode="json")
    s3_endpoint_url = settings.s3_endpoint_url
    s3_bucket = settings.s3_bucket
    b3_config = settings.boto3_config.model_dump(mode="json")
    redis_config = settings.redis_config.model_dump(mode="json")
    redis_dsn = str(settings.redis_url)
    try:
        app.state.store_svc = StorageService(
            s3_endpoint_url,
            s3_config,
            b3_config,
            s3_bucket,
        )
        try:
            await app.state.store_svc.connect()
        except Exception:
            raise
    except Exception as e:
        print(e, flush=True)
    try:
        app.state.cache_svc = CacheService(redis_dsn, redis_config)
        try:
            await app.state.cache_svc.connect()
            try:
                logger.info("Attempting to prime cache metrics on startup...")
                cached_data = await app.state.cache_svc.fetch(mode="startup")
                CACHED_TEMPERATURE.set(cached_data.value)
                CACHE_TIMESTAMP.set(cached_data.timestamp)
                logger.info("Successfully primed cache metrics.")
            except CacheServiceError as e:
                logger.warning("Could not prime cache metrics on startup: %s", e)
        except CacheServiceError:
            raise
    except Exception as e:
        print(e, flush=True)
    sched.start()
    yield
    sched.shutdown()

app = FastAPI(lifespan=lifespan)
app.include_router(metrics_router)

@app.middleware("http")
async def count_requests(request: Request, call_next):
    start_time = time.time()
    resp: Response = await call_next(request)
    process_time_ms = (time.time() - start_time) * 1000
    if request.url.path != "/metrics":
        REQUESTS.labels(
            request.url.path,
            request.method,
            resp.status_code
        ).inc()
        REQUEST_LATENCY.labels(request.url.path, request.method).observe(process_time_ms)
    return resp

@app.get("/version")
async def get_version():
    """Get hivebox version."""
    return {"hivebox": __version__}

def get_cache_svc(request: Request) -> CacheService:
    """Dependency to get the cache service."""
    return request.app.state.cache_svc

def get_store_svc(request: Request) -> StorageService:
    """Dependency to get the storage service."""
    return request.app.state.store_svc

def get_settings_dependency() -> Settings:
    """Dependency to get application settings."""
    return get_settings()

@app.get("/temperature", response_model=TemperatureResult)
async def get_temperature(
    background_tasks: BackgroundTasks,
    cache_svc: CacheService = Depends(get_cache_svc),
    store_svc: StorageService = Depends(get_store_svc),
    settings: Settings = Depends(get_settings_dependency),
):
    mode = "manual"
    temp_svc = TemperatureService(str(settings.osm_base_url), settings.tmp_sensors)

    try:
        cache = await cache_svc.fetch(mode)
        return cache
    except CacheServiceError as e:
        print(f"Cache fetch error: {e}")

    try:
        result = temp_svc.get_average_temperature(mode)
    except TemperatureServiceError as e:
        logger.error("Failed to get average temperature: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not retrieve temperature data from sensors.") from e

    background_tasks.add_task(safe_cache_update, cache_svc, result, mode)

    try:
        await store_svc.store_temperature_result(result, mode)
    except StorageServiceError as e:
        logger.warning("Failed to store temperature result on manual GET: %s", e)

    return result

@app.get("/store")
async def store_temperature(
    background_tasks: BackgroundTasks,
    cache_svc: CacheService = Depends(get_cache_svc),
    store_svc: StorageService = Depends(get_store_svc),
    settings: Settings = Depends(get_settings_dependency),
):
    mode = "manual"
    temp_svc = TemperatureService(str(settings.osm_base_url), settings.tmp_sensors)
    try:
        result = temp_svc.get_average_temperature(mode)
    except TemperatureServiceError as e:
        logger.error("Failed to get average temperature for storing: %s", e)
        raise HTTPException(status_code=500, detail="Could not retrieve temperature data from sensors.") from e

    background_tasks.add_task(safe_cache_update, cache_svc, result, mode)

    try:
        await store_svc.store_temperature_result(result, mode)
    except StorageServiceError as e:
        logger.error("Failed to store temperature result: %s", e)
        raise HTTPException(status_code=500, detail="Failed to store temperature data.") from e

    return {"status": "OK"}

if __name__ == "__main__":  # pragma: no cover
    """Start Uvicorn locally; prod uses Docker CMD."""
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000, log_level="trace")
