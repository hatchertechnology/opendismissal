"""
Test-specific Django settings.
Overrides production settings for testing environment.
"""

# Import base settings - using explicit imports to avoid SonarQube wildcard import warning
# Note: Django test settings must inherit all base settings
from .settings import *  # noqa: F403, F401

# Allow Django test client host early to avoid DisallowedHost during import
ALLOWED_HOSTS = [*ALLOWED_HOSTS, "testserver", "localhost", "127.0.0.1"]  # noqa: F405

# Remove django_ratelimit from INSTALLED_APPS for tests
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "django_ratelimit"]  # noqa: F405

# Use locmem cache backend for tests (fast and doesn't require Redis)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}

# Use database sessions for tests instead of cache-based
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Disable rate limiting during tests
RATELIMIT_ENABLE = False

# Override custom get_host validation in tests to use original implementation
import django.http.request  # noqa: E402
import opendiss.settings as base_settings  # noqa: E402

django.http.request.HttpRequest.get_host = base_settings.original_get_host
