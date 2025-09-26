""" Main entry point for the FastAPI application."""
from fastapi import FastAPI

from .endpoints import temperature, version

app = FastAPI()


@app.get("/")
async def root() -> dict:
    """Root endpoint that returns a message."""
    return {"Hello": "to get the temperature in Berlin, go to /temperature"}


@app.get("/version")
async def get_version() -> dict:
    """Endpoint that returns the version of the application."""
    return {"version": version.get_version()}


@app.get("/temperature")
async def get_temprature() -> dict:
    """Endpoint that returns the average temperature in Berlin."""
    temp = await temperature.get_avg_temp()
    if temp < 10:
        return {"avg_temperature in Berlin is": temp, "status": "Too Cold"}
    elif temp > 37:
        return {"avg_temperature in Berlin is": temp, "status": "Hoo Hot"}
    else:
        return {"avg_temperature in Berlin is": temp, "status": "Good"}
