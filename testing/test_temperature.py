"""Unit tests for the temperature module."""
import sys
import os

# Add the parent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock, MagicMock
import aiohttp

# Import the temperature module AFTER path adjustment
from scr.endpoints import temperature as temp_module


class TestCheckBoxes:
    """Test the check_boxes function."""

    def test_check_boxes_with_recent_data(self):
        """Test boxes with recent measurements are included."""
        recent_time = datetime.now(timezone.utc) - timedelta(hours=1)
        recent_time_str = recent_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        boxes = [
            {"_id": "box1", "lastMeasurementAt": recent_time_str, "name": "Test Box 1"}
        ]

        result = temp_module.check_boxes(boxes)
        assert len(result) == 1
        assert "box1" in result


@pytest.mark.asyncio
async def test_get_boxes_temp_success():
    """Test successful temperature retrieval with proper mocking."""
    # Create a properly mocked async context manager
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "sensors": [
            {
                "title": "Temperature",
                "sensorType": "temperature",
                "lastMeasurement": {"value": "21.5"},
            }
        ]
    }

    # Mock the session.get to return a proper async context manager
    mock_get = AsyncMock()
    mock_get.__aenter__.return_value = mock_response
    mock_get.__aexit__.return_value = None

    # Patch using the imported module directly
    with patch.object(temp_module.aiohttp.ClientSession, "get", return_value=mock_get):
        async with aiohttp.ClientSession() as session:
            box_ids = ["test_box_1"]
            result = await temp_module.get_boxes_temp(box_ids, session)
            assert result == [21.5]


@pytest.mark.asyncio
async def test_get_boxes_success():
    """Test successful box retrieval."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = [
        {
            "_id": "box1",
            "name": "Test Box 1",
            "lastMeasurementAt": "2023-01-01T10:00:00.000Z",
        }
    ]

    mock_get = AsyncMock()
    mock_get.__aenter__.return_value = mock_response
    mock_get.__aexit__.return_value = None

    # Patch using the imported module directly
    with patch.object(temp_module.aiohttp.ClientSession, "get", return_value=mock_get):
        async with aiohttp.ClientSession() as session:
            result = await temp_module.get_boxes(session)
            assert len(result) == 1
            assert result[0]["_id"] == "box1"


@pytest.mark.asyncio
async def test_fallback_temperature_success():
    """Test successful fallback temperature."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {"current": {"temperature_2m": 14.8}}

    mock_get = AsyncMock()
    mock_get.__aenter__.return_value = mock_response
    mock_get.__aexit__.return_value = None

    # Patch using the imported module directly
    with patch.object(temp_module.aiohttp.ClientSession, "get", return_value=mock_get):
        async with aiohttp.ClientSession() as session:
            result = await temp_module.fallback_temperature(session)
            assert result == 14.8


@pytest.mark.asyncio
async def test_get_avg_temp_success():
    """Test the main function with mocked dependencies."""
    # Mock the internal functions that get_avg_temp calls
    with patch.object(temp_module, "get_boxes") as mock_get_boxes, patch.object(
        temp_module, "get_boxes_temp"
    ) as mock_get_boxes_temp:

        # Setup mock returns
        mock_get_boxes.return_value = [
            {
                "_id": "box1",
                "lastMeasurementAt": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                ),
            }
        ]
        mock_get_boxes_temp.return_value = [19.0, 20.0, 21.0]  # Average should be 20.0

        result = await temp_module.get_avg_temp()
        assert result == 20.0


@pytest.mark.asyncio
async def test_get_avg_temp_fallback():
    """Test fallback when no boxes are found."""
    with patch.object(temp_module, "get_boxes") as mock_get_boxes, patch.object(
        temp_module, "fallback_temperature"
    ) as mock_fallback:

        mock_get_boxes.return_value = []  # No boxes found
        mock_fallback.return_value = 15.5

        result = await temp_module.get_avg_temp()
        assert result == 15.5


def test_check_boxes_function():
    """Test the synchronous check_boxes function."""
    # Test with recent data (within 3 hours)
    recent_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    boxes = [
        {
            "_id": "box1",
            "lastMeasurementAt": recent_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }
    ]

    result = temp_module.check_boxes(boxes)
    assert "box1" in result

    # Test with old data (should be excluded - older than 3 hours)
    old_time = datetime.now(timezone.utc) - timedelta(hours=4)
    boxes = [
        {"_id": "box2", "lastMeasurementAt": old_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")}
    ]

    result = temp_module.check_boxes(boxes)
    assert "box2" not in result


def test_get_any_recent_boxes():
    """Test the fallback box selection function."""
    current_time = datetime.now(timezone.utc)

    # Create boxes with different ages
    recent_box = {
        "_id": "recent",
        "lastMeasurementAt": (current_time - timedelta(hours=12)).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        ),
    }

    old_box = {
        "_id": "old",
        "lastMeasurementAt": (current_time - timedelta(hours=36)).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        ),
    }

    boxes = [recent_box, old_box]
    result = temp_module.get_any_recent_boxes(boxes, hours=24)

    assert len(result) == 1
    assert "recent" in result
    assert "old" not in result


# Test for edge cases
@pytest.mark.asyncio
async def test_get_boxes_temp_no_sensors():
    """Test when box has no temperature sensors."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "sensors": [
            {
                "title": "Humidity",
                "sensorType": "humidity",
                "lastMeasurement": {"value": "65"},
            }
        ]
    }

    mock_get = AsyncMock()
    mock_get.__aenter__.return_value = mock_response
    mock_get.__aexit__.return_value = None

    # Patch using the imported module directly
    with patch.object(temp_module.aiohttp.ClientSession, "get", return_value=mock_get):
        async with aiohttp.ClientSession() as session:
            box_ids = ["test_box_1"]
            result = await temp_module.get_boxes_temp(box_ids, session)
            assert result == []  # No temperature sensors found


@pytest.mark.asyncio
async def test_get_boxes_temp_invalid_value():
    """Test when temperature value is invalid."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "sensors": [
            {
                "title": "Temperature",
                "sensorType": "temperature",
                "lastMeasurement": {"value": "invalid"},
            }
        ]
    }

    mock_get = AsyncMock()
    mock_get.__aenter__.return_value = mock_response
    mock_get.__aexit__.return_value = None

    # Patch using the imported module directly
    with patch.object(temp_module.aiohttp.ClientSession, "get", return_value=mock_get):
        async with aiohttp.ClientSession() as session:
            box_ids = ["test_box_1"]
            result = await temp_module.get_boxes_temp(box_ids, session)
            assert result == []  # Invalid temperature value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
