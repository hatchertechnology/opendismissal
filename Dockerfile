# Multi-stage Dockerfile for OpenDismissal Django Application
# Stage 1: Build stage for dependencies and static files
FROM python:3.13-slim AS builder

# Set environment variables for build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_CACHE_DIR=/tmp/uv-cache

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Create application directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies into /app/.venv
RUN uv sync --frozen --no-dev --no-editable

# Copy application code
COPY . .

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && chmod 755 /app/logs

# Collect static files (skip if environment variables not available during build)
RUN mkdir -p /app/staticfiles

# Stage 2: Production runtime image
FROM python:3.13-slim AS production

# Set production environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=opendiss.settings \
    PORT=8000

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r appuser && \
    useradd -r -g appuser -d /app -s /bin/bash appuser

# Create application directory
WORKDIR /app

# Copy the virtual environment from builder stage
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code and static files
COPY --from=builder --chown=appuser:appuser /app /app

# Create and set permissions for required directories
RUN mkdir -p /app/logs /app/staticfiles /app/media && \
    chown -R appuser:appuser /app/logs /app/staticfiles /app/media && \
    chmod 755 /app/logs /app/staticfiles /app/media

# Create startup script with database migrations
RUN echo '#!/bin/bash' > /app/start.sh && \
    echo 'set -e' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo 'echo "Starting OpenDismissal application..."' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo '# Activate virtual environment' >> /app/start.sh && \
    echo 'source /app/.venv/bin/activate' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo '# Wait for database to be ready (simple check)' >> /app/start.sh && \
    echo 'echo "Checking database connectivity..."' >> /app/start.sh && \
    echo 'python manage.py check --deploy --quiet' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo '# Run database migrations' >> /app/start.sh && \
    echo 'echo "Running database migrations..."' >> /app/start.sh && \
    echo 'python manage.py migrate --noinput' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo '# Collect static files (in case of updates)' >> /app/start.sh && \
    echo 'echo "Collecting static files..."' >> /app/start.sh && \
    echo 'python manage.py collectstatic --noinput --clear' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo '# Start the Django application' >> /app/start.sh && \
    echo 'echo "Starting Django server on port ${PORT}..."' >> /app/start.sh && \
    echo 'exec python manage.py runserver 0.0.0.0:${PORT}' >> /app/start.sh && \
    chmod +x /app/start.sh && \
    chown appuser:appuser /app/start.sh

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 8000

# Add health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/admin/login/ || exit 1

# Set the startup command
CMD ["/app/start.sh"]

# Add labels for better container management
LABEL org.opencontainers.image.title="OpenDismissal" \
      org.opencontainers.image.description="School dismissal management system" \
      org.opencontainers.image.vendor="Hatcher Technology" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.source="https://github.com/hatchertechnology/opendismissal"