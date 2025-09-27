FROM python:3.11-alpine

# PYTHONDONTWRITEBYTECODE=1 to prevent Python from writing .pyc files to disk
# PYTHONUNBUFFERED=1 to ensure that the output of Python is sent straight to terminal
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies first
RUN apk add --no-cache gcc=10.3.1-r0 musl-dev=1.2.3-r4 linux-headers=6.1.55-r0

# Copy requirements first for better caching
COPY requirements.txt .

# Create non-root user
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "5555" \
    appuser

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip==24.0 && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Fix permissions
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Use uvicorn directly instead of fastapi run
CMD ["uvicorn", "scr.main:app", "--host", "0.0.0.0", "--port", "8000"]
