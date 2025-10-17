"""This module contains the function to get the average temperature from the OpenSenseMap API."""
from datetime import datetime, timedelta, timezone
import aiohttp
import asyncio
import time

# Import directly from main_monitoring
from ..main_monitoring import (
    TEMPERATURE_API_REQUESTS,
    TEMPERATURE_API_DURATION,
    TEMPERATURE_BOXES_COUNT,
    TEMPERATURE_SENSOR_AGE,
    CURRENT_TEMPERATURE,
    TEMPERATURE_DATA_QUALITY,
    TEMPERATURE_STATUS,
    TEMPERATURE_SERVICE_STATUS,
    TEMPERATURE_FALLBACK_USAGE,
    LAST_SUCCESSFUL_UPDATE,
)


async def get_avg_temp() -> float:
    """
    This is the main function that gets the average temperature from the OpenSenseMap API.
    """
    start_time = time.time()

    try:
        async with aiohttp.ClientSession() as session:
            # Track boxes discovery
            boxes = await get_boxes(session)
            TEMPERATURE_BOXES_COUNT.labels(status="total").set(len(boxes))
            print(f"Total boxes found: {len(boxes)}")

            if not boxes:
                print("No boxes found at all! Service might be down.")
                TEMPERATURE_SERVICE_STATUS.state("degraded")
                TEMPERATURE_API_REQUESTS.labels(
                    api_source="opensensemap", status="no_boxes"
                ).inc()
                return await fallback_temperature(session)

            valid_boxes = check_boxes(boxes)
            TEMPERATURE_BOXES_COUNT.labels(status="valid").set(len(valid_boxes))
            print(f"Valid boxes (recent data): {len(valid_boxes)}")

            if len(valid_boxes) < 2:
                return 503

            # Take up to 5 boxes for better accuracy
            boxes_to_process = valid_boxes[:5]
            TEMPERATURE_BOXES_COUNT.labels(status="processed").set(
                len(boxes_to_process)
            )
            print(
                f"Boxes to process: {[box_id[:8] + '...' for box_id in boxes_to_process]}"
            )

            if not boxes_to_process:
                print("No valid boxes found! Using fallback...")
                TEMPERATURE_SERVICE_STATUS.state("degraded")
                boxes_to_process = get_any_recent_boxes(boxes, hours=24)[:5]

            if not boxes_to_process:
                print("No data available at all! Trying external API...")
                TEMPERATURE_SERVICE_STATUS.state("unavailable")
                return await fallback_temperature(session)

            boxes_temps = await get_boxes_temp(boxes_to_process, session)
            print(f"Temperatures retrieved: {boxes_temps}")

            if not boxes_temps:
                print("No temperature values found! Trying external API...")
                TEMPERATURE_SERVICE_STATUS.state("unavailable")
                return await fallback_temperature(session)

            # Calculate average and set data quality
            avg_temp = sum(boxes_temps) / len(boxes_temps)
            result = round(avg_temp, 2)

            # Update all metrics
            CURRENT_TEMPERATURE.set(result)
            quality = 2 if len(boxes_temps) > 1 else 1
            TEMPERATURE_DATA_QUALITY.set(quality)

            # Set temperature status
            status_label = get_temperature_status(result)
            TEMPERATURE_STATUS.labels(status_label=status_label).set(1)

            TEMPERATURE_SERVICE_STATUS.state("healthy")
            TEMPERATURE_API_REQUESTS.labels(
                api_source="opensensemap", status="success"
            ).inc()
            LAST_SUCCESSFUL_UPDATE.set_to_current_time()

            print(f"Calculated average: {result}°C from {len(boxes_temps)} sources")
            return result

    except Exception:
        TEMPERATURE_API_REQUESTS.labels(api_source="opensensemap", status="error").inc()
        TEMPERATURE_SERVICE_STATUS.state("unavailable")
        raise
    finally:
        duration = time.time() - start_time
        TEMPERATURE_API_DURATION.labels(api_source="opensensemap").observe(duration)


def get_temperature_status(temp: float) -> str:
    """Convert temperature to status category for metrics."""
    if temp < 5:
        return "very_cold"
    elif temp < 10:
        return "cold"
    elif temp >= 30:
        return "hot"
    elif temp >= 25:
        return "warm"
    else:
        return "moderate"


async def get_boxes(session: aiohttp.ClientSession) -> list:
    """This function gets all the boxes from the OpenSenseMap API."""
    start_time = time.time()

    url = "https://api.opensensemap.org/boxes/"
    params = {
        "format": "json",
        "near": "52.5200,13.4050",
        "maxDistance": 50000,
        "phenomenon": "Temperatur",
    }

    try:
        async with session.get(url, params=params, timeout=15) as response:
            if response.status == 200:
                data = await response.json()
                print(f"✓ Successfully fetched {len(data)} boxes")
                TEMPERATURE_API_REQUESTS.labels(
                    api_source="opensensemap_boxes", status="success"
                ).inc()
                return data
            else:
                print(f"Error: HTTP {response.status}")
                TEMPERATURE_API_REQUESTS.labels(
                    api_source="opensensemap_boxes", status=f"http_{response.status}"
                ).inc()
                return []
    except asyncio.TimeoutError:
        print("Timeout fetching boxes list")
        TEMPERATURE_API_REQUESTS.labels(
            api_source="opensensemap_boxes", status="timeout"
        ).inc()
        return []
    except aiohttp.ClientError as e:
        print(f"Network error: {e}")
        TEMPERATURE_API_REQUESTS.labels(
            api_source="opensensemap_boxes", status="network_error"
        ).inc()
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")
        TEMPERATURE_API_REQUESTS.labels(
            api_source="opensensemap_boxes", status="unexpected_error"
        ).inc()
        return []
    finally:
        duration = time.time() - start_time
        TEMPERATURE_API_DURATION.labels(api_source="opensensemap_boxes").observe(
            duration
        )


def check_boxes(boxes) -> list:
    """Checks if the box's sensors last check was within 3 hours."""
    ok_boxes = []
    current_time = datetime.now(timezone.utc)

    for box in boxes:
        if "lastMeasurementAt" not in box or not box["lastMeasurementAt"]:
            continue

        try:
            last_measurement_str = box["lastMeasurementAt"]
            if "." in last_measurement_str:
                last_measurement = datetime.strptime(
                    last_measurement_str, "%Y-%m-%dT%H:%M:%S.%fZ"
                ).replace(tzinfo=timezone.utc)
            else:
                last_measurement = datetime.strptime(
                    last_measurement_str, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)

            time_diff = current_time - last_measurement
            age_hours = time_diff.total_seconds() / 3600

            TEMPERATURE_SENSOR_AGE.observe(age_hours)

            if time_diff <= timedelta(hours=3):
                ok_boxes.append(box["_id"])
                print(f"✓ Box {box['_id'][:8]}... updated {age_hours*60:.0f} min ago")

        except (ValueError, KeyError) as e:
            print(f"✗ Error parsing time for box {box.get('_id', 'unknown')[:8]}: {e}")
            continue

    return ok_boxes


def get_any_recent_boxes(boxes, hours=24):
    """Fallback: get any boxes with data from last X hours."""
    valid_boxes = []
    current_time = datetime.now(timezone.utc)

    for box in boxes:
        if "lastMeasurementAt" not in box or not box["lastMeasurementAt"]:
            continue

        try:
            last_measurement_str = box["lastMeasurementAt"]
            if "." in last_measurement_str:
                last_measurement = datetime.strptime(
                    last_measurement_str, "%Y-%m-%dT%H:%M:%S.%fZ"
                ).replace(tzinfo=timezone.utc)
            else:
                last_measurement = datetime.strptime(
                    last_measurement_str, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)

            time_diff = current_time - last_measurement
            if time_diff <= timedelta(hours=hours):
                valid_boxes.append(box["_id"])
                print(
                    f"↩ Fallback box {box['_id'][:8]}... updated {time_diff.total_seconds()/3600:.1f} hours ago"
                )

        except ValueError as e:
            print(f"Time parsing error for box {box.get('_id', 'unknown')[:8]}: {e}")
            continue

    return valid_boxes


async def get_boxes_temp(box_ids, session: aiohttp.ClientSession) -> list:
    """This function gets the temperature from every box by using their IDs."""

    async def fetch_single_box_temp(box_id: str) -> float | None:
        start_time = time.time()
        try:
            async with session.get(
                f"https://api.opensensemap.org/boxes/{box_id}", timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    temp_values = []
                    for sensor in data.get("sensors", []):
                        sensor_title = sensor.get("title", "").lower()
                        sensor_type = sensor.get("sensorType", "").lower()
                        last_measurement = sensor.get("lastMeasurement")

                        if (
                            any(
                                keyword in sensor_title
                                for keyword in [
                                    "temperature",
                                    "temp",
                                    "t°",
                                    "lufttemperatur",
                                ]
                            )
                            or "temperature" in sensor_type
                        ) and last_measurement:

                            temp_value = last_measurement.get("value")
                            if temp_value and temp_value.strip():
                                try:
                                    temp_float = float(temp_value)
                                    if -20 <= temp_float <= 40:
                                        temp_values.append(temp_float)
                                        print(
                                            f"🌡 Box {box_id[:8]}... temp: {temp_float}°C"
                                        )
                                except ValueError:
                                    continue

                    if temp_values:
                        TEMPERATURE_API_REQUESTS.labels(
                            api_source="opensensemap_sensor", status="success"
                        ).inc()
                        return sum(temp_values) / len(temp_values)
                    else:
                        print(f"❌ No valid temperature data for box {box_id[:8]}...")
                        TEMPERATURE_API_REQUESTS.labels(
                            api_source="opensensemap_sensor", status="no_data"
                        ).inc()
                        return None
                else:
                    print(f"🔴 HTTP {response.status} for box {box_id[:8]}...")
                    TEMPERATURE_API_REQUESTS.labels(
                        api_source="opensensemap_sensor",
                        status=f"http_{response.status}",
                    ).inc()
                    return None
        except asyncio.TimeoutError:
            print(f"⏰ Timeout fetching box {box_id[:8]}...")
            TEMPERATURE_API_REQUESTS.labels(
                api_source="opensensemap_sensor", status="timeout"
            ).inc()
            return None
        except Exception as e:
            print(f"Unexpected error with box {box_id[:8]}: {e}")
            TEMPERATURE_API_REQUESTS.labels(
                api_source="opensensemap_sensor", status="error"
            ).inc()
            return None
        finally:
            duration = time.time() - start_time
            TEMPERATURE_API_DURATION.labels(api_source="opensensemap_sensor").observe(
                duration
            )

    tasks = [fetch_single_box_temp(box_id) for box_id in box_ids]
    results = await asyncio.gather(*tasks)
    return [temp for temp in results if temp is not None]


async def fallback_temperature(session: aiohttp.ClientSession) -> float:
    """Fallback method using a different weather API when OpenSenseMap fails."""
    start_time = time.time()
    TEMPERATURE_FALLBACK_USAGE.inc()
    print("🔄 Trying fallback weather API...")

    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": 52.52,
            "longitude": 13.405,
            "current": "temperature_2m",
            "timezone": "Europe/Berlin",
        }

        async with session.get(url, params=params, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                temp = data.get("current", {}).get("temperature_2m")
                if temp is not None:
                    print(f"✓ Fallback API temperature: {temp}°C")
                    CURRENT_TEMPERATURE.set(float(temp))
                    TEMPERATURE_API_REQUESTS.labels(
                        api_source="openmeteo", status="success"
                    ).inc()
                    TEMPERATURE_DATA_QUALITY.set(0)
                    return float(temp)
            else:
                TEMPERATURE_API_REQUESTS.labels(
                    api_source="openmeteo", status=f"http_{response.status}"
                ).inc()
    except Exception as e:
        print(f"Fallback API also failed: {e}")
        TEMPERATURE_API_REQUESTS.labels(api_source="openmeteo", status="error").inc()
        print("❌ All data sources failed, returning 0.0°C")
        TEMPERATURE_DATA_QUALITY.set(-1)
        return 0.0
    finally:
        duration = time.time() - start_time
        TEMPERATURE_API_DURATION.labels(api_source="openmeteo").observe(duration)
