"""This module contains the function to get the average temperature from the OpenSenseMap API."""
from datetime import datetime, timedelta, timezone  # Fixed: Added timezone
import aiohttp
import asyncio


async def get_avg_temp() -> float:
    """
    This is the main function that gets the average temperature from the OpenSenseMap API.
    """
    async with aiohttp.ClientSession() as session:
        boxes = await get_boxes(session)
        print(f"Total boxes found: {len(boxes)}")

        if not boxes:
            print("No boxes found at all! Service might be down.")
            return await fallback_temperature(session)

        valid_boxes = check_boxes(boxes)
        print(f"Valid boxes (recent data): {len(valid_boxes)}")

        # Take up to 5 boxes for better accuracy
        boxes_to_process = valid_boxes[:5]
        print(
            f"Boxes to process: {[box_id[:8] + '...' for box_id in boxes_to_process]}"
        )

        if not boxes_to_process:
            print("No valid boxes found! Using fallback...")
            # Fallback: try to get any boxes with data from last 24 hours
            boxes_to_process = get_any_recent_boxes(boxes, hours=24)[:5]

        if not boxes_to_process:
            print("No data available at all! Trying external API...")
            return await fallback_temperature(session)

        boxes_temps = await get_boxes_temp(boxes_to_process, session)
        print(f"Temperatures retrieved: {boxes_temps}")

        if not boxes_temps:
            print("No temperature values found! Trying external API...")
            return await fallback_temperature(session)

        # Calculate average
        avg_temp = sum(boxes_temps) / len(boxes_temps)
        result = round(avg_temp, 2)
        print(f"Calculated average: {result}°C")
        return result


async def get_boxes(session: aiohttp.ClientSession) -> list:
    """
    This function gets all the boxes from the OpenSenseMap API.
    """
    url = "https://api.opensensemap.org/boxes/"
    # Larger bbox for Berlin area to get more results
    params = {
        "format": "json",
        "near": "52.5200,13.4050",  # Berlin center
        "maxDistance": 50000,  # 50km radius
        "phenomenon": "Temperatur",  # Only boxes with temperature sensors
    }

    try:
        async with session.get(
            url, params=params, timeout=15
        ) as response:  # Increased timeout
            if response.status == 200:
                data = await response.json()
                print(f"✓ Successfully fetched {len(data)} boxes")
                return data
            else:
                print(f"Error: HTTP {response.status}")
                return []
    except asyncio.TimeoutError:
        print("Timeout fetching boxes list")
        return []
    except aiohttp.ClientError as e:
        print(f"Network error: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return []


def check_boxes(boxes) -> list:
    """
    Checks if the box's sensors last check was within 3 hours and returns a list of box IDs.
    """
    ok_boxes = []
    current_time = datetime.now(timezone.utc)  # Fixed: Using timezone-aware datetime

    for box in boxes:
        if "lastMeasurementAt" not in box or not box["lastMeasurementAt"]:
            continue

        try:
            last_measurement_str = box["lastMeasurementAt"]
            # Handle different time formats
            if "." in last_measurement_str:
                last_measurement = datetime.strptime(
                    last_measurement_str, "%Y-%m-%dT%H:%M:%S.%fZ"
                ).replace(tzinfo=timezone.utc)
            else:
                last_measurement = datetime.strptime(
                    last_measurement_str, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)

            time_diff = current_time - last_measurement

            # Check if measurement is within 3 hours
            if time_diff <= timedelta(hours=3):
                ok_boxes.append(box["_id"])
                print(
                    f"✓ Box {box['_id'][:8]}... updated {time_diff.total_seconds()/60:.0f} min ago"
                )

        except (ValueError, KeyError) as e:
            print(f"✗ Error parsing time for box {box.get('_id', 'unknown')[:8]}: {e}")
            continue

    return ok_boxes


def get_any_recent_boxes(boxes, hours=24):
    """Fallback: get any boxes with data from last X hours."""
    valid_boxes = []
    current_time = datetime.now(timezone.utc)  # Fixed: Using timezone-aware datetime

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
    """
    This function gets the temperature from every box by using their IDs.
    """

    async def fetch_single_box_temp(box_id: str) -> float | None:
        """Fetch temperature for a single box."""
        url = f"https://api.opensensemap.org/boxes/{box_id}"

        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()

                    # Look for temperature sensors
                    temp_values = []
                    for sensor in data.get("sensors", []):
                        sensor_title = sensor.get("title", "").lower()
                        sensor_type = sensor.get("sensorType", "").lower()
                        last_measurement = sensor.get("lastMeasurement")

                        # Check for various temperature sensor names and types
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
                                    # Validate it's a reasonable temperature for Berlin
                                    if -20 <= temp_float <= 40:
                                        temp_values.append(temp_float)
                                        print(
                                            f"🌡 Box {box_id[:8]}... temp: {temp_float}°C"
                                        )
                                except ValueError:
                                    continue

                    # If we found temperatures, use their average for this box
                    if temp_values:
                        return sum(temp_values) / len(temp_values)
                    else:
                        print(f"❌ No valid temperature data for box {box_id[:8]}...")
                        return None
                else:
                    print(f"🔴 HTTP {response.status} for box {box_id[:8]}...")
                    return None

        except asyncio.TimeoutError:
            print(f"⏰ Timeout fetching box {box_id[:8]}...")
            return None
        except aiohttp.ClientError as e:
            print(f"🔌 Error fetching box {box_id[:8]}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error with box {box_id[:8]}: {e}")
            return None

    # Fetch all boxes concurrently
    tasks = [fetch_single_box_temp(box_id) for box_id in box_ids]
    results = await asyncio.gather(*tasks)

    # Filter out None values and return valid temperatures
    return [temp for temp in results if temp is not None]


async def fallback_temperature(session: aiohttp.ClientSession) -> float:
    """
    Fallback method using a different weather API when OpenSenseMap fails.
    """
    print("🔄 Trying fallback weather API...")

    # Using a simple public weather API as fallback
    try:
        # Open-Meteo API (no API key required)
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
                    return float(temp)
    except Exception as e:
        print(f"Fallback API also failed: {e}")

    print("❌ All data sources failed, returning 0.0°C")
    return 0.0
