"""The modules to test the temperature module."""
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import pytest

from ..scr.endpoints.temperature import (
    get_avg_temp,
    get_boxes,
    check_boxes,
    get_boxes_temp,
)


@pytest.mark.asyncio
@patch("HiveBox.scr.endpoints.temperature.requests.Session")
async def test_get_avg_temp(mock_session_class):
    """
    Test the get_avg_temp function to ensure it returns the correct average temperature.
    """
    # Mocked response for get_boxes
    mock_boxes = [
        {
            "_id": "box1",
            "lastMeasurementAt": (datetime.now() - timedelta(hours=1)).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
        },
        {
            "_id": "box2",
            "lastMeasurementAt": (datetime.now() - timedelta(hours=4)).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
        },
    ]

    # Mocked response for get_boxes_temp
    mock_box_data = {
        "sensors": [
            {
                "title": "Temperature",
                "lastMeasurement": {"value": "20.5"},
            }
        ]
    }

    # Configure session.get to return different responses based on URL
    mock_response_boxes = MagicMock()
    mock_response_boxes.status_code = 200
    mock_response_boxes.json.return_value = mock_boxes

    mock_response_temp = MagicMock()
    mock_response_temp.status_code = 200
    mock_response_temp.json.return_value = mock_box_data

    # Mock session.get logic
    mock_session = MagicMock()

    def get_side_effect(url, **kwargs):
        print("Mocked GET called with:", url, kwargs)
        # For the list of boxes (with bbox param)
        if url.endswith("/boxes/") and "bbox" in kwargs.get("params", {}):
            return mock_response_boxes
        # For individual box details
        elif url.startswith("https://api.opensensemap.org/boxes/"):
            return mock_response_temp
        else:
            raise ValueError(f"Unexpected URL: {url}")

    mock_session.get.side_effect = get_side_effect

    mock_session_class.return_value.__enter__.return_value = mock_session

    # Run the function
    result = await get_avg_temp()

    # Only one of the two boxes has recent data, so avg = (0.1 + 20.5)/1 = 20.6
    assert result == 20.5


@patch("HiveBox.scr.endpoints.temperature.requests.Session")
async def test_get_boxes_success(mock_session_class):
    """
    Test the get_boxes function to ensure it returns a list of boxes."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"_id": "box1"}]

    mock_session.get.return_value = mock_response
    mock_session_class.return_value.get = mock_session.get

    result = await get_boxes(mock_session)
    assert result == [{"_id": "box1"}]


@patch("HiveBox.scr.endpoints.temperature.requests.Session")
async def test_get_boxes_failure(
    mock_session_class, capsys: pytest.CaptureFixture[str]
):
    """
    Test the get_boxes function to ensure it handles errors correctly.
    """
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 500

    mock_session.get.return_value = mock_response
    mock_session_class.return_value.get = mock_session.get

    result = await get_boxes(mock_session)
    assert result == []

    captured = capsys.readouterr()
    assert "Error: 500" in captured.out


async def test_check_boxs_valid_recent():
    """
    Test the check_boxs function to ensure it returns a list of box IDs with recent measurements.
    """
    now = datetime.now()
    recent_time = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    boxes = [{"_id": "box1", "lastMeasurementAt": recent_time}]
    result = await check_boxes(boxes)
    assert result == ["box1"]


async def test_check_boxs_old_data():
    """
    Test the check_boxs function to ensure it returns an empty list for old data.
    """
    old_time = (datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    boxs = [{"_id": "box1", "lastMeasurementAt": old_time}]
    result = await check_boxes(boxs)
    assert result == []


async def test_check_boxs_missing_timestamp():
    """
    Test the check_boxs function to ensure it returns an empty list for missing timestamps.
    """
    boxs = [{"_id": "box1"}]
    result = await check_boxes(boxs)
    assert result == []


@patch("HiveBox.scr.endpoints.temperature.requests.Session")
async def test_get_boxes_temp_valid(mock_session_class):
    """
    Test the get_boxes_temp function to ensure it returns a list of temperatures.
    """
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "sensors": [
            {"title": "Temperature", "lastMeasurement": {"value": "24.5"}},
            {"title": "Humidity", "lastMeasurement": {"value": "55"}},
        ]
    }
    mock_session.get.return_value = mock_response
    mock_session_class.return_value.get = mock_session.get

    box_ids = ["box1"]
    temps = await get_boxes_temp(box_ids, mock_session)
    assert temps == ["24.5"]


@patch("HiveBox.scr.endpoints.temperature.requests.Session")
async def test_get_boxes_temp_no_temp_sensor(mock_session_class):
    """
    Test the get_boxes_temp function to ensure it returns
     an empty list if no temperature sensor is found.
    """
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "sensors": [{"title": "Humidity", "lastMeasurement": {"value": "55"}}]
    }
    mock_session.get.return_value = mock_response
    mock_session_class.return_value.get = mock_session.get

    box_ids = ["box1"]
    temps = await get_boxes_temp(box_ids, mock_session)
    assert temps == []


@patch("HiveBox.scr.endpoints.temperature.requests.Session")
async def test_get_boxes_temp_empty_boxes(mock_session_class):
    """Test the get_boxes_temp function to ensure it returns
    an empty list if no box IDs are provided.
    """
    mock_session_class.return_value.get = MagicMock()
    mock_session = MagicMock()
    box_ids = []
    temps = await get_boxes_temp(box_ids, mock_session)
    assert temps == []
