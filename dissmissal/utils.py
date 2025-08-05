"""
OpenDismissal Utility Functions

Utility functions for IP extraction, audit logging, and other common operations.
Author: Derek Hayes
"""

import logging
from django.utils import timezone
from django.core.cache import cache
from django.db import models


# Set up audit logging
audit_logger = logging.getLogger("dissmissal.audit")


def get_client_ip(request):
    """
    Extract client IP address from request, accounting for proxies.
    Essential for FERPA compliance and security audit trails.

    Args:
        request: Django HttpRequest object

    Returns:
        str: Client IP address
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # Get the first IP in the chain (original client)
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")

    # Return localhost if no IP found (development/testing)
    return ip or "127.0.0.1"


def log_audit_event(user, action, ip_address, details=None):
    """
    Log audit events for FERPA compliance and security monitoring.

    Args:
        user: Django User object who performed the action
        action: String describing the action taken
        ip_address: IP address of the user
        details: Dictionary of additional details to log
    """
    log_entry = {
        "user_id": user.id,
        "username": user.username,
        "user_full_name": user.get_full_name() or user.username,
        "action": action,
        "timestamp": timezone.now().isoformat(),
        "ip_address": ip_address,
        "details": details or {},
    }

    audit_logger.info(f"User {user.username} performed {action}", extra=log_entry)


def get_dashboard_stats(cache_timeout=30):
    """
    Calculate dashboard statistics for display with independent caching.
    Used by both views and API endpoints.

    Args:
        cache_timeout: Cache timeout in seconds (default: 30s for real-time accuracy)

    Returns:
        dict: Statistics about current dismissal status
    """
    from .models import Student, PickupEvent

    # Independent stats caching for better performance
    stats_cache_key = "dashboard_stats_global"
    stats = cache.get(stats_cache_key)
    
    if stats is None:
        today = timezone.now().date()

        stats = {
            "total_active": Student.objects.filter(is_active=True).count(),
            "waiting": Student.objects.filter(is_active=True, current_status="WAITING").count(),
            "parent_arrived": Student.objects.filter(
                is_active=True, current_status="PARENT_ARRIVED"
            ).count(),
            "picked_up": Student.objects.filter(is_active=True, current_status="PICKED_UP").count(),
            "events_today": PickupEvent.objects.filter(timestamp__date=today).count(),
            "last_updated": timezone.now(),
        }

        # Calculate percentages
        if stats["total_active"] > 0:
            stats["waiting_percent"] = round((stats["waiting"] / stats["total_active"]) * 100, 1)
            stats["arrived_percent"] = round((stats["parent_arrived"] / stats["total_active"]) * 100, 1)
            stats["picked_up_percent"] = round((stats["picked_up"] / stats["total_active"]) * 100, 1)
        else:
            stats["waiting_percent"] = stats["arrived_percent"] = stats["picked_up_percent"] = 0

        # Cache stats independently from dashboard data for real-time accuracy
        cache.set(stats_cache_key, stats, timeout=cache_timeout)

    return stats


def validate_staff_permissions(user, required_permissions=None):
    """
    Validate staff member has required permissions for dismissal operations.

    Args:
        user: Django User object
        required_permissions: List of required permission strings

    Returns:
        bool: True if user has required permissions
    """
    if not user.is_authenticated:
        return False

    if not user.is_staff:
        return False

    if not user.is_active:
        return False

    if required_permissions:
        return user.has_perms(required_permissions)

    return True


def format_pickup_event_for_display(pickup_event):
    """
    Format pickup event data for template display.

    Args:
        pickup_event: PickupEvent model instance

    Returns:
        dict: Formatted event data for templates
    """
    return {
        "id": pickup_event.id,
        "student_name": pickup_event.student.name,
        "student_grade": pickup_event.student.grade,
        "event_type": pickup_event.get_event_type_display(),
        "event_type_code": pickup_event.event_type,
        "staff_name": pickup_event.staff_member.get_full_name()
        or pickup_event.staff_member.username,
        "timestamp": pickup_event.timestamp,
        "time_ago": timezone.now() - pickup_event.timestamp,
        "dismissal_code": pickup_event.dismissal_code_used,
        "notes": pickup_event.notes,
        "css_class": {
            "PARENT_ARRIVED": "text-warning",
            "STUDENT_PICKED_UP": "text-success",
            "CANCELLED": "text-danger",
        }.get(pickup_event.event_type, "text-muted"),
    }


def get_cache_key(prefix, user_id=None, **kwargs):
    """
    Generate consistent cache keys for the dismissal system.

    Args:
        prefix: Cache key prefix
        user_id: Optional user ID for user-specific caching
        **kwargs: Additional parameters to include in cache key

    Returns:
        str: Generated cache key
    """
    key_parts = [prefix]

    if user_id:
        key_parts.append(f"user_{user_id}")

    for key, value in sorted(kwargs.items()):
        if value:
            key_parts.append(f"{key}_{value}")

    return "_".join(key_parts)


def clear_dashboard_cache(user_id=None):
    """
    Clear dashboard-related cache entries with targeted approach.

    Args:
        user_id: Optional user ID to clear specific user cache
    """
    # Always clear the global stats cache when dashboard data changes
    cache.delete("dashboard_stats_global")
    
    # Django's default cache doesn't support delete_pattern
    # We'll implement a targeted cache clearing mechanism
    if hasattr(cache, 'delete_pattern'):
        if user_id:
            # Clear specific user cache
            pattern = f"dashboard_user_{user_id}_*"
            cache.delete_pattern(pattern)
        else:
            # Clear all dashboard cache
            cache.delete_pattern("dashboard_*")
    else:
        # Targeted fallback - clear common dashboard cache keys instead of cache.clear()
        if user_id:
            # Clear common dashboard cache keys for the specific user
            common_filters = [
                ("all", "all", ""),
                ("WAITING", "all", ""), 
                ("PARENT_ARRIVED", "all", ""),
                ("PICKED_UP", "all", ""),
            ]
            for status, grade, search in common_filters:
                cache_key = generate_dashboard_cache_key(user_id, status, grade, search)
                cache.delete(cache_key)
        else:
            # Clear common dashboard cache keys for all users (up to reasonable limit)
            # Note: This approach is more targeted than cache.clear() but may not catch all keys
            # Consider using a cache backend that supports pattern deletion for full coverage
            for user_idx in range(1, 101):  # Assume max 100 concurrent users for cache clearing
                common_filters = [
                    ("all", "all", ""),
                    ("WAITING", "all", ""),
                    ("PARENT_ARRIVED", "all", ""),
                    ("PICKED_UP", "all", ""),
                ]
                for status, grade, search in common_filters:
                    cache_key = generate_dashboard_cache_key(user_idx, status, grade, search)
                    cache.delete(cache_key)


def sanitize_input(text, max_length=None):
    """
    Sanitize user input to prevent XSS and other security issues.

    Args:
        text: Input text to sanitize
        max_length: Optional maximum length limit

    Returns:
        str: Sanitized text
    """
    if not text:
        return ""

    import html

    # Strip whitespace and escape HTML
    sanitized = html.escape(text.strip())

    # Limit length if specified
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized


def generate_dashboard_cache_key(user_id, status_filter="all", grade_filter="all", search_query=""):
    """
    Generate cache key for dashboard data based on filters.

    Args:
        user_id: User ID for user-specific caching
        status_filter: Status filter value
        grade_filter: Grade filter value
        search_query: Search query string

    Returns:
        str: Generated cache key
    """
    return get_cache_key(
        "dashboard",
        user_id=user_id,
        status=status_filter,
        grade=grade_filter,
        search=search_query.replace(" ", "_") if search_query else None,
    )


def validate_dismissal_code_format(code):
    """
    Validate dismissal code format without checking database.

    Args:
        code: Dismissal code to validate

    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    import re

    if not code:
        return False, "Dismissal code is required"

    code = code.strip().upper()

    if len(code) < 6 or len(code) > 8:
        return False, "Dismissal code must be 6-8 characters long"

    if not re.match(r"^[A-Z0-9]+$", code):
        return False, "Dismissal code can only contain letters and numbers"

    return True, ""


def format_time_ago(timestamp):
    """
    Format timestamp as human-readable time ago string.

    Args:
        timestamp: DateTime object

    Returns:
        str: Human-readable time ago string
    """
    now = timezone.now()
    diff = now - timestamp

    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"

    hours = diff.seconds // 3600
    if hours > 0:
        return f"{hours} hour{'s' if hours > 1 else ''} ago"

    minutes = diff.seconds // 60
    if minutes > 0:
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"

    return "Just now"


# Cache the optimized queryset configuration to avoid repeated construction
_OPTIMIZED_QUERYSET_CONFIG = None

def get_student_query_optimized():
    """
    Get optimized queryset for students with proper relations.
    Uses cached configuration to avoid repeated query construction.

    Returns:
        QuerySet: Optimized Student queryset
    """
    global _OPTIMIZED_QUERYSET_CONFIG
    from .models import Student, PickupEvent

    if _OPTIMIZED_QUERYSET_CONFIG is None:
        _OPTIMIZED_QUERYSET_CONFIG = models.Prefetch(
            "pickup_events",
            queryset=PickupEvent.objects.select_related("staff_member").order_by("-timestamp"),
        )

    return Student.objects.prefetch_related(_OPTIMIZED_QUERYSET_CONFIG)
