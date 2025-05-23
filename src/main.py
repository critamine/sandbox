"""Main entry point for the application."""

import prometheus_client
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, HTTPException
from pydantic import AliasChoices, BaseModel, Field, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict
from hivebox.cache import CacheService, CacheMessages, CacheServiceError
from hivebox import __version__
from hivebox.temperature import TemperatureService, TemperatureServiceError, TemperatureResult
from hivebox import SENSEBOX_TEMP_SENSORS as SB_SENS

class RedisConfig(BaseModel):
    encoding: str
    decode_responses: bool
    socket_connect_timeout: Optional[int] = None
    retry_on_timeout: Optional[bool] = None
    socket_timeout: Optional[int] = None

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='../.env', 
        env_file_encoding='utf-8', 
        extra='ignore'
    )
    redis_url: RedisDsn = Field(
        'redis://localhost:6379/0',
        validation_alias=AliasChoices('REDIS_URL'),
    )
    redis_config: RedisConfig = Field(
    {
        "encoding": "utf-8",
        "decode_responses": True,
    },
        validation_alias=AliasChoices('REDIS'),
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        redis_config = Settings().redis_config.model_dump(mode="json")
        redis_dsn = str(Settings().redis_url)
        cache_svc = CacheService(redis_dsn, redis_config)
        app.state.cache_svc = cache_svc
        try:
            await cache_svc.connect()
        except CacheServiceError:
            print(CacheMessages.REDIS_CONN_FAIL, flush=True)
    except Exception:
        pass
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/version")
async def get_version():
    """Get hivebox version."""
    return {"hivebox": __version__}

@app.get("/temperature", response_model=TemperatureResult)
async def get_temperature(request: Request):
    temp_svc = TemperatureService(SB_SENS)
    cache_svc = app.state.cache_svc
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
        await cache_svc.update(result)
    except CacheServiceError as e:
        print(f"Cache update error: {e}")

    return result

@app.get("/metrics")
async def metrics():
    """Expose Prometheus metrics."""
    return Response(
        content=prometheus_client.generate_latest(),
        media_type="text/plain"
    )

if __name__ == "__main__": # pragma: no cover
    """Start Uvicorn locally; prod uses Docker CMD."""
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000, log_level="trace")
