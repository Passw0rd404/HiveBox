"""Version endpoint for the FastAPI application."""
import logging

logger = logging.getLogger(__name__)

# Remove the prometheus dependency
# from ..main_monitoring import VERSION_INFO


def get_version() -> str:
    """Returns the current version of the application."""
    version_str = "0.6.0"
    # Use regular logging instead of prometheus
    logger.info("Application version: %s", version_str)
    return version_str
