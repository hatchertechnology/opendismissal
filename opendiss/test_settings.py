"""
Test-specific Django settings.
Overrides production settings for testing environment.
"""

from .settings import *

# Remove django_ratelimit from INSTALLED_APPS for tests
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "django_ratelimit"]

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
