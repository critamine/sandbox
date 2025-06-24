"""Main entry point for the application."""

import prometheus_client
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from contextlib import asynccontextmanager, suppress
from fastapi import BackgroundTasks, FastAPI, Request, Response, HTTPException
from hivebox.config import get_settings
from hivebox.cache import CacheService, CacheServiceError
from hivebox.store import StorageService, StorageServiceError
from hivebox import __version__
from hivebox.temperature import (
    TemperatureService,
    TemperatureServiceError,
    TemperatureResult,
)
from hivebox import SENSEBOX_TEMP_SENSORS as SB_SENS

sched = AsyncIOScheduler()

async def poll(job_id: str):
    try:
        result = await app.state.store_svc.get_stored_temperature()
        if result is None:
            last_temp, age = None, None
        else:
            last_temp, age = result

        if last_temp is not None and age < 300:
            next_delay = 300 - age
        else:
            temp_svc = TemperatureService(SB_SENS)
            new_temp = temp_svc.get_average_temperature()
            await app.state.store_svc.store_temperature_result(new_temp)
            with suppress(CacheServiceError):
                await app.state.cache_svc.update(new_temp)
            next_delay = 300
            print("Delay set", flush=True)
    except Exception:
        raise

    sched.reschedule_job(
        job_id,
        trigger=IntervalTrigger(seconds=next_delay)
    )

job = sched.add_job(
    poll,
    IntervalTrigger(seconds=30),
    args=[ "dynamic_poll" ],
    id="dynamic_poll",
)

async def safe_cache_update(cache_svc, result):
    try:
        await cache_svc.update(result)
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
    except Exception:
        raise
    try:
        app.state.cache_svc = CacheService(redis_dsn, redis_config)
        try:
            await app.state.cache_svc.connect()
        except CacheServiceError:
            raise
    except Exception as e:
        print(e, flush=True)
    sched.start()
    yield
    sched.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/version")
async def get_version():
    """Get hivebox version."""
    return {"hivebox": __version__}

@app.get("/temperature", response_model=TemperatureResult)
async def get_temperature(request: Request, background_tasks: BackgroundTasks):
    temp_svc = TemperatureService(SB_SENS)
    cache_svc = app.state.cache_svc
    store_svc = app.state.store_svc
    try:
        cache = await cache_svc.fetch()
        return cache
    except CacheServiceError as e:
        print(f"Cache fetch error: {e}")

    try:
        result = temp_svc.get_average_temperature()
    except TemperatureServiceError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    try:
        await store_svc.store_temperature_result(result)
    except StorageServiceError as e:
        print(f"Store update error: {e}")

    background_tasks.add_task(safe_cache_update, cache_svc, result)

    return result

@app.get("/store")
async def store_temperature(request: Request, background_tasks: BackgroundTasks):
    temp_svc = TemperatureService(SB_SENS)
    cache_svc = app.state.cache_svc
    store_svc = app.state.store_svc
    try:
        result = temp_svc.get_average_temperature()
    except TemperatureServiceError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    
    try:
        await store_svc.store_temperature_result(result)
    except StorageServiceError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    background_tasks.add_task(safe_cache_update, cache_svc, result)

    return {"status": "OK"}

@app.get("/metrics")
async def metrics():
    """Expose Prometheus metrics."""
    return Response(
        content=prometheus_client.generate_latest(), media_type="text/plain"
    )

if __name__ == "__main__":  # pragma: no cover
    """Start Uvicorn locally; prod uses Docker CMD."""
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000, log_level="trace")
