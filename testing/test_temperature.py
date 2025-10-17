"""Unit tests for the temperature module."""
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
import pytest

from src.endpoints.temperature import (
    get_avg_temp,
    get_temperature_status,
    check_boxes,
    get_any_recent_boxes,
    get_boxes_temp,
    fallback_temperature,
)


class TestTemperatureStatus:
    """Test temperature status categorization."""

    def test_very_cold_temperature(self):
        """Test temperature below 5°C returns 'very_cold'."""
        assert get_temperature_status(4.9) == "very_cold"
        assert get_temperature_status(-10) == "very_cold"

    def test_cold_temperature(self):
        """Test temperature between 5-10°C returns 'cold'."""
        assert get_temperature_status(5.0) == "cold"
        assert get_temperature_status(7.5) == "cold"
        assert get_temperature_status(9.9) == "cold"

    def test_moderate_temperature(self):
        """Test temperature between 10-25°C returns 'moderate'."""
        assert get_temperature_status(10.0) == "moderate"
        assert get_temperature_status(15.0) == "moderate"
        assert get_temperature_status(24.9) == "moderate"

    def test_warm_temperature(self):
        """Test temperature between 25-30°C returns 'warm'."""
        assert get_temperature_status(25.0) == "warm"
        assert get_temperature_status(27.5) == "warm"
        assert get_temperature_status(29.9) == "warm"

    def test_hot_temperature(self):
        """Test temperature above 30°C returns 'hot'."""
        assert get_temperature_status(30.0) == "hot"
        assert get_temperature_status(35.0) == "hot"
        assert get_temperature_status(40.0) == "hot"


class TestCheckBoxes:
    """Test box validation logic."""

    def test_check_boxes_valid_recent_data(self):
        """Test boxes with recent data are included."""
        boxes = [
            {
                "_id": "box1",
                "lastMeasurementAt": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                ),
            },
            {
                "_id": "box2",
                "lastMeasurementAt": (
                    datetime.now(timezone.utc) - timedelta(hours=2)
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        ]

        valid_boxes = check_boxes(boxes)
        assert len(valid_boxes) == 2
        assert "box1" in valid_boxes
        assert "box2" in valid_boxes

    def test_check_boxes_old_data_excluded(self):
        """Test boxes with old data are excluded."""
        boxes = [
            {
                "_id": "old_box",
                "lastMeasurementAt": (
                    datetime.now(timezone.utc) - timedelta(hours=4)
                ).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            }
        ]

        valid_boxes = check_boxes(boxes)
        assert len(valid_boxes) == 0

    def test_check_boxes_missing_timestamp(self):
        """Test boxes without timestamp are excluded."""
        boxes = [
            {
                "_id": "no_timestamp_box",
                # Missing lastMeasurementAt
            }
        ]

        valid_boxes = check_boxes(boxes)
        assert len(valid_boxes) == 0

    def test_check_boxes_invalid_timestamp_format(self):
        """Test boxes with invalid timestamp format are handled gracefully."""
        boxes = [
            {"_id": "invalid_time_box", "lastMeasurementAt": "invalid-date-format"}
        ]

        # Should not raise an exception
        valid_boxes = check_boxes(boxes)
        assert len(valid_boxes) == 0


class TestGetAnyRecentBoxes:
    """Test fallback box selection logic."""

    def test_get_any_recent_boxes_within_timeframe(self):
        """Test boxes within extended timeframe are included."""
        boxes = [
            {
                "_id": "recent_box",
                "lastMeasurementAt": (
                    datetime.now(timezone.utc) - timedelta(hours=12)
                ).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            },
            {
                "_id": "old_box",
                "lastMeasurementAt": (
                    datetime.now(timezone.utc) - timedelta(hours=25)
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        ]

        valid_boxes = get_any_recent_boxes(boxes, hours=24)
        assert len(valid_boxes) == 1
        assert "recent_box" in valid_boxes


class TestGetBoxesTemp:
    """Test temperature fetching from individual boxes."""

    @pytest.mark.asyncio
    async def test_get_boxes_temp_success(self):
        """Test successful temperature retrieval from boxes."""
        # Mock the prometheus metrics that are used in get_boxes_temp
        with patch("src.endpoints.temperature.TEMPERATURE_API_REQUESTS"), patch(
            "src.endpoints.temperature.TEMPERATURE_API_DURATION"
        ):

            # Create response mock
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={
                    "sensors": [
                        {
                            "title": "Temperature Sensor",
                            "sensorType": "temperature",
                            "lastMeasurement": {"value": "22.5"},
                        }
                    ]
                }
            )

            # Create a proper async context manager using MagicMock
            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_cm.__aexit__ = AsyncMock(return_value=None)

            # Create session mock
            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_cm)

            box_ids = ["box1", "box2"]
            temperatures = await get_boxes_temp(box_ids, mock_session)

            assert len(temperatures) == 2
            assert all(temp == 22.5 for temp in temperatures)

    @pytest.mark.asyncio
    async def test_get_boxes_temp_no_valid_data(self):
        """Test handling of boxes with no valid temperature data."""
        with patch("src.endpoints.temperature.TEMPERATURE_API_REQUESTS"), patch(
            "src.endpoints.temperature.TEMPERATURE_API_DURATION"
        ):

            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={
                    "sensors": [
                        {
                            "title": "Humidity Sensor",  # Wrong sensor type
                            "sensorType": "humidity",
                            "lastMeasurement": {"value": "65"},
                        }
                    ]
                }
            )

            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_cm)

            box_ids = ["box1"]
            temperatures = await get_boxes_temp(box_ids, mock_session)

            assert len(temperatures) == 0

    @pytest.mark.asyncio
    async def test_get_boxes_temp_http_error(self):
        """Test handling of HTTP errors."""
        with patch("src.endpoints.temperature.TEMPERATURE_API_REQUESTS"), patch(
            "src.endpoints.temperature.TEMPERATURE_API_DURATION"
        ):

            mock_response = MagicMock()
            mock_response.status = 404

            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_cm)

            box_ids = ["box1"]
            temperatures = await get_boxes_temp(box_ids, mock_session)

            assert len(temperatures) == 0

    @pytest.mark.asyncio
    async def test_get_boxes_temp_timeout(self):
        """Test handling of timeout errors."""
        with patch("src.endpoints.temperature.TEMPERATURE_API_REQUESTS"), patch(
            "src.endpoints.temperature.TEMPERATURE_API_DURATION"
        ):

            mock_session = MagicMock()
            mock_session.get = MagicMock(side_effect=asyncio.TimeoutError())

            box_ids = ["box1"]
            temperatures = await get_boxes_temp(box_ids, mock_session)

            assert len(temperatures) == 0


class TestFallbackTemperature:
    """Test fallback temperature API."""

    @pytest.mark.asyncio
    async def test_fallback_temperature_success(self):
        """Test successful fallback temperature retrieval."""
        # Mock ALL prometheus metrics used in fallback_temperature
        with patch(
            "src.endpoints.temperature.CURRENT_TEMPERATURE"
        ) as mock_current_temp, patch(
            "src.endpoints.temperature.TEMPERATURE_DATA_QUALITY"
        ) as mock_quality, patch(
            "src.endpoints.temperature.TEMPERATURE_API_REQUESTS"
        ), patch(
            "src.endpoints.temperature.TEMPERATURE_FALLBACK_USAGE"
        ) as mock_fallback, patch(
            "src.endpoints.temperature.TEMPERATURE_API_DURATION"
        ):

            # Create response mock
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={"current": {"temperature_2m": 18.7}}
            )

            # Create a proper async context manager using MagicMock
            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_cm.__aexit__ = AsyncMock(return_value=None)

            # Create session mock
            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_cm)

            temperature = await fallback_temperature(mock_session)

            assert temperature == 18.7
            mock_current_temp.set.assert_called_once_with(18.7)
            mock_quality.set.assert_called_once_with(0)
            mock_fallback.inc.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_temperature_api_failure(self):
        """Test fallback when API fails completely."""
        with patch("src.endpoints.temperature.TEMPERATURE_FALLBACK_USAGE"), patch(
            "src.endpoints.temperature.TEMPERATURE_API_REQUESTS"
        ), patch("src.endpoints.temperature.TEMPERATURE_API_DURATION"), patch(
            "src.endpoints.temperature.TEMPERATURE_DATA_QUALITY"
        ):

            mock_session = MagicMock()
            mock_session.get = MagicMock(side_effect=Exception("API unavailable"))

            temperature = await fallback_temperature(mock_session)

            assert temperature == 0.0


class TestGetAvgTempIntegration:
    """Integration tests for the main get_avg_temp function."""

    @pytest.mark.asyncio
    async def test_get_avg_temp_success(self):
        """Test successful temperature averaging with valid boxes."""
        mock_boxes = [
            {
                "_id": "box1",
                "lastMeasurementAt": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                ),
            },
            {
                "_id": "box2",
                "lastMeasurementAt": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            },
        ]

        # Mock all dependencies
        with patch("src.endpoints.temperature.get_boxes") as mock_get_boxes, patch(
            "src.endpoints.temperature.get_boxes_temp"
        ) as mock_get_boxes_temp, patch(
            "src.endpoints.temperature.TEMPERATURE_BOXES_COUNT"
        ), patch(
            "src.endpoints.temperature.CURRENT_TEMPERATURE"
        ) as mock_current_temp, patch(
            "src.endpoints.temperature.TEMPERATURE_DATA_QUALITY"
        ) as mock_quality, patch(
            "src.endpoints.temperature.TEMPERATURE_STATUS"
        ), patch(
            "src.endpoints.temperature.TEMPERATURE_SERVICE_STATUS"
        ), patch(
            "src.endpoints.temperature.TEMPERATURE_API_REQUESTS"
        ), patch(
            "src.endpoints.temperature.LAST_SUCCESSFUL_UPDATE"
        ), patch(
            "src.endpoints.temperature.TEMPERATURE_API_DURATION"
        ):

            mock_get_boxes.return_value = mock_boxes
            mock_get_boxes_temp.return_value = [
                22.0,
                23.0,
                24.0,
            ]  # Average should be 23.0

            result = await get_avg_temp()

            assert result == 23.0
            mock_get_boxes.assert_called_once()
            mock_get_boxes_temp.assert_called_once()
            mock_current_temp.set.assert_called_once_with(23.0)
            mock_quality.set.assert_called_once_with(2)  # 3 sources = quality 2

    @pytest.mark.asyncio
    async def test_get_avg_temp_no_boxes(self):
        """Test behavior when no boxes are found."""
        with patch("src.endpoints.temperature.get_boxes") as mock_get_boxes, patch(
            "src.endpoints.temperature.fallback_temperature"
        ) as mock_fallback, patch(
            "src.endpoints.temperature.TEMPERATURE_BOXES_COUNT"
        ), patch(
            "src.endpoints.temperature.TEMPERATURE_SERVICE_STATUS"
        ), patch(
            "src.endpoints.temperature.TEMPERATURE_API_REQUESTS"
        ), patch(
            "src.endpoints.temperature.TEMPERATURE_API_DURATION"
        ):

            mock_get_boxes.return_value = []  # No boxes found
            mock_fallback.return_value = 19.5

            result = await get_avg_temp()

            assert result == 19.5
            mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_avg_temp_not_enough_valid_boxes(self):
        """Test behavior when not enough valid boxes are available."""
        mock_boxes = [
            {
                "_id": "box1",
                "lastMeasurementAt": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                ),
            }
            # Only one valid box - less than required minimum of 2
        ]

        with patch("src.endpoints.temperature.get_boxes") as mock_get_boxes, patch(
            "src.endpoints.temperature.check_boxes"
        ) as mock_check_boxes, patch(
            "src.endpoints.temperature.TEMPERATURE_BOXES_COUNT"
        ), patch(
            "src.endpoints.temperature.TEMPERATURE_API_DURATION"
        ):

            mock_get_boxes.return_value = mock_boxes
            mock_check_boxes.return_value = ["box1"]  # Only one valid box

            result = await get_avg_temp()

            assert result == 503  # Service unavailable

    @pytest.mark.asyncio
    async def test_get_avg_temp_exception_handling(self):
        """Test exception handling in main function."""
        with patch("src.endpoints.temperature.get_boxes") as mock_get_boxes, patch(
            "src.endpoints.temperature.TEMPERATURE_API_REQUESTS"
        ) as mock_requests, patch(
            "src.endpoints.temperature.TEMPERATURE_SERVICE_STATUS"
        ), patch(
            "src.endpoints.temperature.TEMPERATURE_API_DURATION"
        ):

            mock_get_boxes.side_effect = Exception("Test error")

            with pytest.raises(Exception, match="Test error"):
                await get_avg_temp()

            # Verify metrics were updated even on error
            mock_requests.labels.assert_called_with(
                api_source="opensensemap", status="error"
            )


# Test configuration
def pytest_configure(config):
    """Pytest configuration hook."""
    # Mark all tests as asyncio by default
    config.option.asyncio_mode = "auto"


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
