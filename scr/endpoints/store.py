"""
Storage module for MinIO temperature data operations.
Contains the MinIOStorage class for handling temperature data storage.
"""

import datetime
import json
import logging
import os
from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


class MinIOStorage:
    """MinIO storage client for temperature data operations."""

    def __init__(self):
        """Initialize MinIO storage client with environment configuration."""
        # Get configuration from environment variables
        self.endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
        self.access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.secure = os.getenv("MINIO_SECURE", "false").lower() == "true"

        logger.info("Connecting to MinIO at: %s", self.endpoint)

        try:
            self.minio_client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure
            )
            self.bucket_name = "temperature-data"
            self._ensure_bucket_exists()
            logger.info("MinIO storage initialized successfully")
        except Exception as init_error:
            logger.error("Failed to initialize MinIO storage: %s", init_error)
            raise

    def _ensure_bucket_exists(self):
        """Ensure the MinIO bucket exists."""
        try:
            if not self.minio_client.bucket_exists(self.bucket_name):
                self.minio_client.make_bucket(self.bucket_name)
                logger.info("Created bucket: %s", self.bucket_name)
            else:
                logger.debug("Bucket already exists: %s", self.bucket_name)
        except S3Error as bucket_error:
            logger.error("MinIO bucket error: %s", bucket_error)
            raise

    async def store_temperature_data(self, temperature_data: float,
                                   sensor_count: int,
                                   storage_type: str = "manual"):
        """
        Store temperature data to MinIO.

        Args:
            temperature_data: The temperature value to store
            sensor_count: Number of sensors used (0 for fallback)
            storage_type: "manual", "scheduled", or "manual_fallback"

        Returns:
            bool: True if storage was successful, False otherwise
        """
        try:
            # Determine data quality based on sensor count
            if sensor_count > 3:
                data_quality = "high"
            elif sensor_count > 0:
                data_quality = "medium"
            else:
                data_quality = "low"

            # Prepare data for storage with enhanced metadata
            storage_data = {
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "temperature": temperature_data,
                "sensor_count": sensor_count,
                "storage_type": storage_type,
                "data_quality": data_quality,
                "source": "opensensemap" if storage_type != "manual_fallback" else "fallback_api"
            }

            # Create descriptive filename
            timestamp = datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')
            filename = f"{storage_type}-{timestamp}.json"

            # Upload to MinIO
            self.minio_client.put_object(
                self.bucket_name,
                filename,
                json.dumps(storage_data, indent=2).encode('utf-8'),
                len(json.dumps(storage_data))
            )

            logger.info(
                "Temperature data stored: %s - %.2f°C from %d sensors",
                filename, temperature_data, sensor_count
            )
            return True

        except S3Error as storage_error:
            logger.error("MinIO storage error: %s", storage_error)
            return False
        except Exception as unexpected_error:
            logger.error("Unexpected storage error: %s", unexpected_error)
            return False


# Global storage instance
storage_client = MinIOStorage()
