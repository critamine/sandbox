"""Main entry point for the application."""

import prometheus_client
from fastapi import FastAPI, Response, HTTPException
from hivebox import __version__
from hivebox.temperature import TemperatureService, TemperatureServiceError
from hivebox import SENSEBOX_TEMP_SENSORS as SB_DATA

app = FastAPI()

@app.get("/version")
async def get_version():
    """Get hivebox version."""
    return {"hivebox": __version__}

@app.get("/temperature")
async def get_temperature():
    """Get average temperature."""
    try:
        service = TemperatureService(SB_DATA)
        result = service.get_average_temperature()
        return {
            "value": result.value,
            "status": result.status
        }
    except TemperatureServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
async def metrics():
    """Expose Prometheus metrics."""
    return Response(
        content=prometheus_client.generate_latest(),
        media_type="text/plain"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
