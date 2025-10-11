"""Main monitoring module that initializes all Prometheus metrics."""
from prometheus_client import (
    Counter, Histogram, Gauge, Enum, Info, generate_latest
)
from prometheus_client.core import REGISTRY

# Root endpoint metrics
ROOT_REQUESTS = Counter(
    'root_requests_total',
    'Total requests to root endpoint'
)

ROOT_REQUEST_DURATION = Histogram(
    'root_request_duration_seconds', 
    'Root endpoint request duration'
)

# Temperature API metrics
TEMPERATURE_API_REQUESTS = Counter(
    'temperature_api_requests_total',
    'Total number of temperature API requests',
    ['api_source', 'status']
)

TEMPERATURE_API_DURATION = Histogram(
    'temperature_api_duration_seconds',
    'Temperature API request duration',
    ['api_source']
)

TEMPERATURE_BOXES_COUNT = Gauge(
    'temperature_boxes_count',
    'Number of temperature sensor boxes',
    ['status']  # total, valid, processed
)

TEMPERATURE_SENSOR_AGE = Histogram(
    'temperature_sensor_age_hours',
    'Age of temperature sensor data in hours',
    buckets=[1, 3, 6, 12, 24, 48, 72, 168]
)

CURRENT_TEMPERATURE = Gauge(
    'current_temperature_celsius',
    'Current average temperature in Berlin'
)

TEMPERATURE_DATA_QUALITY = Gauge(
    'temperature_data_quality',
    'Quality indicator for temperature data (2=high, 1=medium, 0=fallback, -1=error)'
)

TEMPERATURE_STATUS = Gauge(
    'temperature_status',
    'Current temperature status category',
    ['status_label']  # very_cold, cold, moderate, warm, hot
)

TEMPERATURE_SERVICE_STATUS = Enum(
    'temperature_service_status',
    'Current status of temperature service',
    states=['healthy', 'degraded', 'unavailable']
)

TEMPERATURE_FALLBACK_USAGE = Counter(
    'temperature_fallback_usage_total',
    'Number of times fallback temperature API was used'
)

LAST_SUCCESSFUL_UPDATE = Gauge(
    'last_successful_update_timestamp',
    'Timestamp of last successful temperature update'
)

# Version metrics
VERSION_INFO = Info(
    'app_version',
    'Application version information'
)

def initialize_metrics():
    """Initialize metrics with default values."""
    TEMPERATURE_SERVICE_STATUS.state('healthy')
    TEMPERATURE_DATA_QUALITY.set(-1)  # Start with error state until first update
    CURRENT_TEMPERATURE.set(0.0)
    
    # Initialize all status categories to 0
    for status in ['very_cold', 'cold', 'moderate', 'warm', 'hot']:
        TEMPERATURE_STATUS.labels(status_label=status).set(0)

def get_metrics():
    """Return all metrics in Prometheus format."""
    return generate_latest(REGISTRY)

# Initialize metrics when module is imported
initialize_metrics()