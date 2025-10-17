FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy only requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip==24.0 \
    && pip install --no-cache-dir -r requirements.txt

# Create non-root user early (but use it later)
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "5555" \
    appuser

# Copy application code with proper ownership
# Copy src as a package, not just its contents
COPY --chown=appuser:appuser src/ /app/src/

# Switch to non-root user
USER appuser

EXPOSE 8000

# Use uvicorn with production settings
# Run as module: src.main:app instead of main:app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
