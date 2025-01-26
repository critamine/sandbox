"""Main entry point for the application."""

from fastapi import FastAPI
from hivebox import __version__
from hivebox.temperature import get_average_temperature

app = FastAPI()

@app.get("/version")
async def get_version():
    """Get hivebox version."""
    return {"hivebox": __version__}

@app.get("/temperature")
async def get_temperature():
    """Get average temperature."""
    return {"temperature": get_average_temperature()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
