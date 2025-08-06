# OpenDismissal Django Application Dockerfile
# Multi-stage build for production-ready container with security best practices

# Build stage - Install dependencies and build static assets
FROM python:3.13-slim AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install UV package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Set work directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies into virtual environment
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

RUN mkdir -p /app/logs

# Set required environment variables for build stage
ENV DEBUG=False \
    DATABASE_URL=sqlite:///build.sqlite3 \
    ALLOWED_HOSTS=localhost

# Collect static files (requires Django settings to be available)
RUN --mount=type=secret,id=BUILD_DSKEY,env=SECRET_KEY uv run python manage.py collectstatic --noinput --clear

# Production stage - Minimal runtime image
FROM python:3.13-slim AS production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=opendiss.settings

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install UV package manager in production stage
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Create non-root user for security
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set work directory
WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code and static files
COPY --from=builder --chown=appuser:appuser /app /app

# Create logs and media directories with proper permissions
RUN mkdir -p /app/logs /app/media && chown -R appuser:appuser /app/logs /app/media

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check using curl - Updated to use django-health-check endpoint
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ht/ || exit 1

# Default command - can be overridden in docker-compose or kubernetes
CMD ["sh", "-c", "uv run python manage.py migrate && uv run daphne -b 0.0.0.0 -p 8000 opendiss.asgi:application"]
