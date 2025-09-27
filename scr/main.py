""" Main entry point for the FastAPI application."""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

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
async def get_temperature():
    """Endpoint that returns the average temperature in Berlin."""
    try:
        temp = await temperature.get_avg_temp()

        # Handle the case where no data was found
        if temp == 0.0:
            return JSONResponse(
                status_code=503,
                content={
                    "avg_temperature_in_berlin": temp,
                    "status": "Service Unavailable",
                    "note": "Temperature services are currently unavailable. Please try again later.",
                },
            )

        # Determine status based on temperature
        if temp < 5:
            status = "Very Cold"
        elif temp < 10:
            status = "Cold"
        elif temp > 30:
            status = "Hot"
        elif temp > 25:
            status = "Warm"
        else:
            status = "Moderate"

        return {"avg_temperature_in_berlin": temp, "status": status, "unit": "°C"}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e
