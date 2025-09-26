FROM python:alpine
# PYTHONDONTWRITEBYTECODE=1 to prevent Python from writing .pyc files to disk
# PYTHONUNBUFFERED=1 to ensure that the output of Python is sent straight to terminal (e.g. for docker logs) without being buffered
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# copy system dependencies
COPY ./requirements.txt /app/requirements.txt

# making system user to avoid running as root
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "5555" \
    appuser

# enable pip cache and install dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    python -m pip install --no-cache-dir -r requirements.txt

USER appuser

COPY . /app/

EXPOSE 8000

# run the application
CMD ["fastapi", "run", "scr/main.py", "--port", "8000"]
