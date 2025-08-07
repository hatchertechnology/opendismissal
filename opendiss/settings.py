"""
Django settings for OpenDismissal project.

Production-ready configuration with security, performance, and compliance features.
Author: Elena Rodriguez
"""

from pathlib import Path
import dj_database_url
from decouple import config
from django.core.management.utils import get_random_secret_key

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = config("DEBUG", default=False, cast=bool)
if DEBUG:
    # Development mode - use SECRET_KEY from env or generate a random one
    SECRET_KEY = config("SECRET_KEY", default=None)
    if not SECRET_KEY:
        SECRET_KEY = get_random_secret_key()
else:
    # Production mode - require SECRET_KEY to be explicitly set
    SECRET_KEY = config("SECRET_KEY", default=None)
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY environment variable must be set in production.")
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost").split(",")

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "django_ratelimit",  # For rate limiting
    "health_check",  # Django health check
    "health_check.db",  # Database health check
    "health_check.cache",  # Cache health check
    "health_check.contrib.migrations",  # Migrations health check
    "csp",  # Content Security Policy support
    # Local apps
    "dissmissal",
]

# Security middleware for production
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "opendiss.middleware.SSLRedirectExemptMiddleware",  # Custom SSL redirect with exemptions
    "csp.middleware.CSPMiddleware",  # Content Security Policy
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Static file serving for production
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.gzip.GZipMiddleware",  # Response compression for performance
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "opendiss.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "opendiss.wsgi.application"

# Database configuration with environment variables
DATABASES = {
    "default": dj_database_url.config(
        default=config("DATABASE_URL", default="sqlite:///db.sqlite3")
    )
}

# Database performance optimizations
if "postgresql" in DATABASES["default"]["ENGINE"]:
    # Connection pooling - use CONN_MAX_AGE as top-level setting, not in OPTIONS
    DATABASES["default"]["CONN_MAX_AGE"] = 600
    # psycopg3 connection options (if needed)
    DATABASES["default"]["OPTIONS"] = {
        "sslmode": "prefer",  # SSL connection preference
    }
elif "sqlite" in DATABASES["default"]["ENGINE"]:
    DATABASES["default"]["OPTIONS"] = {
        "timeout": 20,  # Prevent database lock timeouts
    }

# Cache configuration with fallback
try:
    import importlib.util

    if importlib.util.find_spec("django_redis") is not None:
        REDIS_URL = config("REDIS_URL", default="redis://127.0.0.1:6379/1")
        CACHES = {
            "default": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": REDIS_URL,
                "KEY_PREFIX": "opendismissal",
                "TIMEOUT": 300,  # 5 minutes default
                "OPTIONS": {
                    "CLIENT_CLASS": "django_redis.client.DefaultClient",
                },
            }
        }
    else:
        raise ImportError("django_redis not available")
except ImportError:
    # Fallback to locmem cache if Redis is not available
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "opendismissal-fallback",
            "TIMEOUT": 300,
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Authentication settings
LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/dissmissal/"
LOGOUT_REDIRECT_URL = "/admin/login/"

# Internationalization and time zone
LANGUAGE_CODE = "en-us"
TIME_ZONE = config("TIME_ZONE", default="America/New_York")  # Adjust for school timezone
USE_I18N = True
USE_TZ = True

# Static files configuration
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# WhiteNoise static files storage (configurable via environment)
STATICFILES_STORAGE = config(
    "STATICFILES_STORAGE", default="django.contrib.staticfiles.storage.StaticFilesStorage"
)

# WhiteNoise configuration for production optimization
WHITENOISE_USE_FINDERS = DEBUG  # Use finders in development, not in production
WHITENOISE_AUTOREFRESH = DEBUG  # Auto-refresh in development only
WHITENOISE_SKIP_COMPRESS_EXTENSIONS = [
    "jpg",
    "jpeg",
    "png",
    "gif",
    "webp",
    "zip",
    "gz",
    "tgz",
    "bz2",
    "tbz",
    "xz",
    "br",
]
WHITENOISE_MAX_AGE = config(
    "WHITENOISE_MAX_AGE", default=31536000, cast=int
)  # 1 year cache by default

# Media files configuration
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Session configuration for security
SESSION_COOKIE_HTTPONLY = config("SESSION_COOKIE_HTTPONLY", default=True, cast=bool)
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=not DEBUG, cast=bool)
SESSION_COOKIE_SAMESITE = config("SESSION_COOKIE_SAMESITE", default="Lax")
SESSION_COOKIE_AGE = config("SESSION_COOKIE_AGE", default=86400, cast=int)

# Session engine configuration - configurable for K8s deployment
SESSION_ENGINE = config("SESSION_ENGINE", default="django.contrib.sessions.backends.cache")
SESSION_CACHE_ALIAS = "default"

# Session optimization settings
SESSION_SAVE_EVERY_REQUEST = config("SESSION_SAVE_EVERY_REQUEST", default=False, cast=bool)

# CSRF configuration
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=not DEBUG, cast=bool)
CSRF_COOKIE_SAMESITE = "Lax"

# CSRF trusted origins for HTTPS (configurable via environment)
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="",
    cast=lambda v: [origin.strip() for origin in v.split(",") if origin.strip()],
)

# Security headers (configurable for production)
SECURE_BROWSER_XSS_FILTER = config("SECURE_BROWSER_XSS_FILTER", default=not DEBUG, cast=bool)
SECURE_CONTENT_TYPE_NOSNIFF = config("SECURE_CONTENT_TYPE_NOSNIFF", default=not DEBUG, cast=bool)
X_FRAME_OPTIONS = config("X_FRAME_OPTIONS", default="DENY")
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000 if not DEBUG else 0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=not DEBUG, cast=bool)
SECURE_HSTS_PRELOAD = config("SECURE_HSTS_PRELOAD", default=not DEBUG, cast=bool)
# Using custom SSLRedirectExemptMiddleware instead of Django's built-in SSL redirect
# This allows us to exempt health check endpoints while maintaining security
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=not DEBUG, cast=bool)
SECURE_PROXY_SSL_HEADER = tuple(config("SECURE_PROXY_SSL_HEADER", default="HTTP_X_FORWARDED_PROTO,https").split(",")) if config("SECURE_PROXY_SSL_HEADER", default="") else None
SECURE_REFERRER_POLICY = config("SECURE_REFERRER_POLICY", default="strict-origin-when-cross-origin")

# Exclude health check endpoints from SSL redirects for Kubernetes probes
# This allows internal HTTP health checks while maintaining HTTPS for user traffic
SECURE_SSL_REDIRECT_EXEMPT = [
    r'^/ht/',  # Health check endpoint
]

# Logging configuration for audit trail
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "dissmissal_audit.log",
            "formatter": "verbose",
        },
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "dissmissal.audit": {
            "handlers": ["file"],
            "level": "INFO",
            "propagate": True,
        },
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
    },
}

# Rate limiting configuration
RATELIMIT_ENABLE = not DEBUG



# Content Security Policy Configuration (Added for security audit fixes)
# Resolves browser console errors and implements OWASP best practices
# Using django-csp v4.0+ format
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': ("'self'",),
        'script-src': (
            "'self'",
            "'unsafe-inline'",  # Required for Django admin
            "'unsafe-eval'",    # Required for some Django admin features
        ),
        'style-src': (
            "'self'",
            "'unsafe-inline'",  # Required for Django admin styles
        ),
        'font-src': ("'self'", "data:"),
        'img-src': ("'self'", "data:", "https:"),
        'connect-src': ("'self'",),  # For AJAX/WebSocket connections
        'frame-ancestors': ("'none'",),  # Equivalent to X-Frame-Options: DENY
        'base-uri': ("'self'",),
        'form-action': ("'self'",),
        'upgrade-insecure-requests': not DEBUG,  # Upgrade HTTP to HTTPS in production
    }
}

# Cross-Origin Policies (fixes COOP browser warnings)
SECURE_CROSS_ORIGIN_OPENER_POLICY = config("SECURE_CROSS_ORIGIN_OPENER_POLICY", default="same-origin")

# Additional security hardening
DATA_UPLOAD_MAX_MEMORY_SIZE = config("DATA_UPLOAD_MAX_MEMORY_SIZE", default=5242880, cast=int)  # 5MB
SESSION_EXPIRE_AT_BROWSER_CLOSE = config("SESSION_EXPIRE_AT_BROWSER_CLOSE", default=True, cast=bool)
CSRF_USE_SESSIONS = config("CSRF_USE_SESSIONS", default=True, cast=bool)  # Store CSRF in session

# Permissions Policy (for additional browser feature control)
# Note: This would require custom middleware to implement
PERMISSIONS_POLICY = {
    "camera": "none",
    "microphone": "none",
    "geolocation": "none",
    "payment": "none",
    "usb": "none",
}
