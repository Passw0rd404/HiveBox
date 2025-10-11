"""Version endpoint for the FastAPI application."""
from ..main_monitoring import VERSION_INFO

def get_version() -> str:
    """Returns the current version of the application."""
    version_str = "0.5.0"
    VERSION_INFO.info({'version': version_str})
    return version_str