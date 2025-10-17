"""Main entry point for the FastAPI application."""
import asyncio
import datetime
import json
import logging
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

# Import monitoring metrics
from .main_monitoring import (
    ROOT_REQUESTS,
    ROOT_REQUEST_DURATION,
    VERSION_INFO,
    initialize_metrics,
)

from .endpoints import temperature, version
from .endpoints.store import storage_client
from .endpoints.cache import valkey_cache

logger = logging.getLogger(__name__)

app = FastAPI(title="Berlin Temperature API", version="0.5.0")


async def get_temperature_with_cache() -> float:
    """
    Get temperature with Valkey cache layer.

    Returns:
        float: Temperature value (may be from cache or fresh)
    """
    # Try to get from cache first
    cached_temp = await valkey_cache.get_temperature()
    if cached_temp is not None:
        logger.info("Returning temperature from cache: %.2f°C", cached_temp)
        return cached_temp

    # If not in cache, get fresh data
    logger.info("Cache miss, fetching fresh temperature data")
    fresh_temp = await temperature.get_avg_temp()

    # Cache the result (only if it's valid data)
    if fresh_temp != 503 and fresh_temp != 0.0:
        await valkey_cache.set_temperature(fresh_temp, ttl=300)  # 5 minutes
        logger.info("Fresh temperature cached: %.2f°C", fresh_temp)

    return fresh_temp


async def scheduled_temperature_store():
    """
    Automatic scheduled storage every 5 minutes.
    This runs in the background continuously.
    """
    while True:
        try:
            logger.info("Starting scheduled temperature storage")

            # Get temperature (will use cache if available)
            temperature_data = await get_temperature_with_cache()

            # Only store if we have valid data (not 503 service unavailable)
            if temperature_data != 503:
                # Determine storage type and sensor count
                if temperature_data == 0.0:
                    storage_type = "scheduled_fallback"
                    sensor_count = 0
                else:
                    storage_type = "scheduled"
                    sensor_count = 5  # Typical number from temperature.py logic

                # Store to MinIO
                success = await storage_client.store_temperature_data(
                    temperature_data=temperature_data,
                    sensor_count=sensor_count,
                    storage_type=storage_type,
                )

                if success:
                    logger.info(
                        "Scheduled storage successful: %.2f°C", temperature_data
                    )
                else:
                    logger.error("Scheduled storage failed")
            else:
                logger.warning(
                    "Skipping scheduled storage - temperature service unavailable"
                )

        except Exception as error:
            logger.error("Error in scheduled storage: %s", str(error))

        # Wait 5 minutes before next storage
        await asyncio.sleep(300)  # 300 seconds = 5 minutes


@app.on_event("startup")
async def startup():
    """Initialize application on startup."""
    initialize_metrics()
    # Set version info
    VERSION_INFO.info({"version": version.get_version()})

    # Start the scheduled storage task
    asyncio.create_task(scheduled_temperature_store())
    logger.info("Scheduled temperature storage started (every 5 minutes)")

    # Add Prometheus metrics endpoint
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=[".*admin.*", "/metrics"],
        env_var_name="ENABLE_METRICS",
        inprogress_name="inprogress",
        inprogress_labels=True,
    )
    instrumentator.instrument(app).expose(app)


@app.middleware("http")
async def monitor_all_requests(request: Request, call_next):
    """Middleware to monitor all HTTP requests."""
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    # Track request duration for all endpoints
    if request.url.path == "/":
        ROOT_REQUEST_DURATION.observe(duration)
    elif request.url.path == "/version":
        # Version duration handled in version.py
        pass
    elif request.url.path == "/temperature":
        # Temperature duration handled in temperature.py
        pass

    return response


@app.get("/")
async def root() -> dict:
    """Root endpoint that returns a message."""
    start_time = time.time()

    try:
        ROOT_REQUESTS.inc()
        return {
            "Hello": "to get the temperature in Berlin, go to /temperature",
            "endpoints": {
                "temperature": "GET /temperature - Get current temperature",
                "version": "GET /version - Get API version",
                "store": "POST /store - Trigger immediate temperature storage",
                "store_status": "GET /store/status - Check storage service status",
                "store_test": "GET /store/test - Test MinIO connection",
                "valkey_status": "GET /valkey/status - Check Valkey cache status",
                "valkey_info": "GET /valkey/info - Get Valkey server info",
                "health": "GET /healthz - Health check",
                "ready": "GET /readyz - Readiness check",
            },
            "features": {
                "automatic_storage": "Every 5 minutes",
                "manual_storage": "Via POST /store endpoint",
                "caching": "Valkey cache with 5-minute TTL",
            },
        }
    finally:
        duration = time.time() - start_time
        ROOT_REQUEST_DURATION.observe(duration)


@app.get("/version")
async def get_version() -> dict:
    """Endpoint that returns the version of the application."""
    version_str = version.get_version()
    return {"version": version_str}


@app.get("/readyz")
async def get_readyz():
    """Readiness probe endpoint."""
    # Use cache for readiness check
    ready = await get_temperature_with_cache()
    if ready == 503:
        return JSONResponse(
            status_code=503,
            content={
                "status": "Service Unavailable",
                "note": "Temperature services are currently unavailable. Please try again later.",
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "Service available",
            "note": "Temperature services are currently available.",
        },
    )


@app.get("/healthz")
async def health_check():
    """Liveness probe endpoint."""
    return {"status": "healthy"}


@app.get("/temperature")
async def get_temperature():
    """Endpoint that returns the average temperature in Berlin with caching."""
    try:
        # This will use cache automatically
        temp = await get_temperature_with_cache()

        # Handle the case where no data was found
        if temp == 0.0:
            return JSONResponse(
                status_code=503,
                content={
                    "avg_temperature_in_berlin": temp,
                    "status": "Service Unavailable",
                    "note": "Temperature services are currently unavailable. Please try again later.",
                    "source": "fallback",
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

        # Check if data came from cache
        cache_source = (
            "cache" if await valkey_cache.get_temperature() is not None else "live"
        )

        return {
            "avg_temperature_in_berlin": temp,
            "status": status,
            "unit": "°C",
            "source": cache_source,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(error)}"
        ) from error


@app.post("/store")
async def trigger_immediate_store():
    """
    Trigger immediate storage of temperature data to MinIO.
    This will bypass cache and get fresh data.

    Returns:
        JSONResponse: Success or error response with details
    """
    try:
        logger.info("Manual store endpoint triggered - bypassing cache")

        # Bypass cache for manual storage to ensure fresh data
        temperature_data = await temperature.get_avg_temp()

        # Handle service unavailable case (503)
        if temperature_data == 503:
            logger.error("Temperature service unavailable - not enough valid boxes")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "Temperature service unavailable - not enough valid sensor data",
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                },
            )

        # Determine storage type and sensor count based on temperature quality
        if temperature_data == 0.0:
            # Fallback data - low quality
            storage_type = "manual_fallback"
            sensor_count = 0
            data_quality = "low"
            logger.warning("Using fallback temperature data (low quality)")
        else:
            # Normal data - estimate sensor count based on typical behavior
            storage_type = "manual"
            sensor_count = 6  # Typical number from temperature.py logic
            data_quality = "normal"
            logger.info("Storing normal temperature data: %.2f°C", temperature_data)

        # Store immediately to MinIO
        success = await storage_client.store_temperature_data(
            temperature_data=temperature_data,
            sensor_count=sensor_count,
            storage_type=storage_type,
        )

        # Update cache with fresh data
        if success and temperature_data != 0.0:
            await valkey_cache.set_temperature(temperature_data, ttl=300)
            logger.info("Cache updated with fresh data: %.2f°C", temperature_data)

        if success:
            logger.info("Manual storage successful: %.2f°C", temperature_data)
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "message": "Temperature data stored immediately to MinIO",
                    "temperature": temperature_data,
                    "sensor_count": sensor_count,
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "storage_type": storage_type,
                    "data_quality": data_quality,
                    "cache_updated": True,
                },
            )

        logger.error("Manual storage failed: MinIO storage error")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Failed to store temperature data to MinIO",
                "timestamp": datetime.datetime.utcnow().isoformat(),
            },
        )

    except Exception as endpoint_error:
        logger.error("Error in manual storage endpoint: %s", str(endpoint_error))
        raise HTTPException(
            status_code=500,
            detail=f"Error triggering immediate storage: {str(endpoint_error)}",
        ) from endpoint_error


@app.get("/store/status")
async def get_store_status():
    """
    Get information about the storage service status.

    Useful for debugging and monitoring.

    Returns:
        JSONResponse: Storage service status information
    """
    try:
        # Test temperature service availability (use cache)
        temperature_data = await get_temperature_with_cache()

        # Test MinIO connectivity
        minio_available = False
        try:
            minio_available = storage_client.minio_client.bucket_exists(
                storage_client.bucket_name
            )
        except Exception as minio_error:
            logger.debug("MinIO connectivity check failed: %s", minio_error)
            minio_available = False

        # Get cache status
        cache_status = await valkey_cache.get_storage_status()

        status_info = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "temperature_service": "available"
            if temperature_data != 503
            else "unavailable",
            "minio_storage": "available" if minio_available else "unavailable",
            "valkey_cache": cache_status.get("available", False),
            "current_temperature": temperature_data
            if temperature_data != 503
            else None,
            "data_quality": "fallback" if temperature_data == 0.0 else "normal",
            "automatic_storage": "active (every 5 minutes)",
        }

        if temperature_data == 503:
            status_info["data_quality"] = "unavailable"

        return JSONResponse(status_code=200, content=status_info)

    except Exception as status_error:
        logger.error("Error getting store status: %s", str(status_error))
        raise HTTPException(
            status_code=500, detail=f"Error getting storage status: {str(status_error)}"
        ) from status_error


@app.get("/store/test")
async def test_store_connection():
    """
    Test endpoint to verify MinIO connection and permissions.

    Returns:
        JSONResponse: Test connection results
    """
    try:
        # Test MinIO connection by creating a test object
        test_data = {
            "test": True,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "message": "Test connection to MinIO",
        }

        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        test_filename = f"test-connection-{timestamp}.json"

        storage_client.minio_client.put_object(
            storage_client.bucket_name,
            test_filename,
            json.dumps(test_data).encode("utf-8"),
            len(json.dumps(test_data)),
        )

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "MinIO connection test successful",
                "test_file": test_filename,
                "timestamp": datetime.datetime.utcnow().isoformat(),
            },
        )

    except Exception as test_error:
        logger.error("MinIO connection test failed: %s", str(test_error))
        raise HTTPException(
            status_code=500, detail=f"MinIO connection test failed: {str(test_error)}"
        ) from test_error


@app.get("/storage/info")
async def get_storage_info():
    """
    Get information about storage operations.
    """
    return {
        "automatic_storage": {
            "enabled": True,
            "interval": "5 minutes",
            "purpose": "Regular temperature data collection",
        },
        "manual_storage": {
            "enabled": True,
            "endpoint": "POST /store",
            "purpose": "On-demand temperature data storage",
        },
        "storage_backend": "MinIO",
        "caching": {
            "enabled": True,
            "backend": "Valkey",
            "ttl": "5 minutes",
            "purpose": "Reduce API calls and improve performance",
        },
        "data_retention": "All historical data stored with timestamps",
    }


@app.get("/valkey/status")
async def get_valkey_status():
    """Get detailed Valkey cache status."""
    try:
        cache_status = await valkey_cache.get_storage_status()
        cache_stats = await valkey_cache.get_cache_stats()

        return JSONResponse(
            status_code=200,
            content={
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "cache_engine": "valkey",
                "status": cache_status,
                "statistics": cache_stats,
            },
        )
    except Exception as error:
        logger.error("Error getting Valkey status: %s", str(error))
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Error getting Valkey status: {str(error)}",
            },
        )


@app.get("/valkey/info")
async def get_valkey_info():
    """Get Valkey server information."""
    try:
        if valkey_cache.client:
            info = valkey_cache.client.info()
            return JSONResponse(
                status_code=200,
                content={
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "valkey_info": {
                        "version": info.get("valkey_version", "unknown"),
                        "mode": info.get("valkey_mode", "unknown"),
                        "os": info.get("os", "unknown"),
                        "uptime_in_seconds": info.get("uptime_in_seconds", 0),
                        "connected_clients": info.get("connected_clients", 0),
                        "used_memory": info.get("used_memory", 0),
                        "used_memory_human": info.get("used_memory_human", "0B"),
                    },
                },
            )
        else:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "message": "Valkey not connected"},
            )
    except Exception as error:
        logger.error("Error getting Valkey info: %s", str(error))
        raise HTTPException(
            status_code=500, detail=f"Error getting Valkey info: {str(error)}"
        ) from error


@app.delete("/cache/clear")
async def clear_cache():
    """Clear the temperature cache (admin endpoint)."""
    try:
        if valkey_cache.client:
            valkey_cache.client.delete("temperature:current")
            logger.info("Temperature cache cleared manually")

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Temperature cache cleared",
                "timestamp": datetime.datetime.utcnow().isoformat(),
            },
        )
    except Exception as error:
        logger.error("Error clearing cache: %s", str(error))
        raise HTTPException(
            status_code=500, detail=f"Error clearing cache: {str(error)}"
        ) from error


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
