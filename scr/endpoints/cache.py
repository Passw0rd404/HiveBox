"""
Valkey cache service for temperature data caching.
Uses the official Valkey Python client.
"""
import json
import logging
from valkey import Valkey
from valkey.exceptions import ValkeyError
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class ValkeyCache:
    """Valkey cache client for temperature data using official Valkey client."""

    def __init__(self):
        """Initialize Valkey cache client."""
        self.host = os.getenv("VALKEY_HOST", "valkey")
        self.port = int(os.getenv("VALKEY_PORT", "6379"))
        self.password = os.getenv("VALKEY_PASSWORD", "")
        self.db = int(os.getenv("VALKEY_DB", "0"))

        logger.info("Connecting to Valkey at: %s:%s", self.host, self.port)

        try:
            self.client = Valkey(
                host=self.host,
                port=self.port,
                password=self.password if self.password else None,
                db=self.db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=30
            )
            # Test connection
            self.client.ping()
            logger.info("Valkey cache initialized successfully")
        except ValkeyError as e:
            logger.error("Failed to connect to Valkey: %s", e)
            self.client = None

    async def get_temperature(self) -> float | None:
        """
        Get cached temperature data.
        
        Returns:
            float | None: Cached temperature or None if not found/expired
        """
        if not self.client:
            return None

        try:
            cached_data = self.client.get("temperature:current")
            if cached_data:
                data = json.loads(cached_data)
                logger.debug("Cache hit for temperature data")
                return data.get("temperature")
            logger.debug("Cache miss for temperature data")
            return None
        except ValkeyError as e:
            logger.error("Error reading from Valkey cache: %s", e)
            return None

    async def set_temperature(self, temperature: float, ttl: int = 300) -> bool:
        """
        Cache temperature data with TTL.
        
        Args:
            temperature: Temperature value to cache
            ttl: Time to live in seconds (default: 5 minutes)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.client:
            return False

        try:
            cache_data = {
                "temperature": temperature,
                "timestamp": self._current_timestamp(),
                "source": "valkey_cache"
            }
            success = self.client.setex(
                "temperature:current",
                ttl,
                json.dumps(cache_data)
            )
            if success:
                logger.debug("Temperature cached successfully in Valkey: %.2f°C", temperature)
            return bool(success)
        except ValkeyError as e:
            logger.error("Error writing to Valkey cache: %s", e)
            return False

    async def get_storage_status(self) -> dict:
        """
        Get Valkey cache storage status.
        
        Returns:
            dict: Cache status information
        """
        if not self.client:
            return {"available": False, "error": "Not connected"}

        try:
            info = self.client.info()
            return {
                "available": True,
                "engine": "valkey",
                "version": info.get("valkey_version", "unknown"),
                "used_memory": info.get("used_memory", 0),
                "connected_clients": info.get("connected_clients", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(info)
            }
        except ValkeyError as e:
            return {"available": False, "error": str(e)}

    def _calculate_hit_rate(self, info: dict) -> float:
        """Calculate cache hit rate."""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        return round((hits / total * 100), 2) if total > 0 else 0.0

    def _current_timestamp(self) -> str:
        """Get current timestamp string."""
        return datetime.utcnow().isoformat()

    async def get_cache_stats(self) -> dict:
        """
        Get detailed cache statistics.
        
        Returns:
            dict: Detailed cache statistics
        """
        if not self.client:
            return {"error": "Valkey not connected"}

        try:
            # Get multiple metrics at once
            cache_key = "temperature:current"
            ttl = self.client.ttl(cache_key)
            memory_stats = self.client.info("memory")
            stats = self.client.info("stats")

            return {
                "temperature_key_ttl": ttl,
                "used_memory_human": memory_stats.get("used_memory_human", "0B"),
                "instantaneous_ops_per_sec": stats.get("instantaneous_ops_per_sec", 0),
                "total_commands_processed": stats.get("total_commands_processed", 0)
            }
        except ValkeyError as e:
            return {"error": str(e)}


# Global Valkey cache instance
valkey_cache = ValkeyCache()
