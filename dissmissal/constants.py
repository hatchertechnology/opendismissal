"""
OpenDismissal Constants

Constants used throughout the OpenDismissal application to reduce string duplication
and maintain consistency.
"""

# Demo data teacher names - used in generate_demo_data command
DEMO_TEACHER_NAMES = ["Mrs. Smith", "Mr. Davis", "Ms. Garcia", "Mrs. Wilson", "Ms. Martinez"]

# Demo data configuration for realistic grade distribution
DEMO_GRADES = ["1st", "2nd", "3rd", "4th", "5th"]

# Cache key prefixes for consistency
CACHE_PREFIXES = {
    "DASHBOARD_STATS": "dashboard_stats_global",
    "DASHBOARD_USER": "dashboard_user",
    "DASHBOARD": "dashboard",
}

# Common dashboard filter combinations for cache clearing
COMMON_DASHBOARD_FILTERS = [
    ("all", "all", ""),
    ("WAITING", "all", ""),
    ("PARENT_ARRIVED", "all", ""),
    ("PICKED_UP", "all", ""),
]

# Maximum number of concurrent users assumed for cache clearing operations
MAX_CONCURRENT_USERS_FOR_CACHE = 100

# Model field lengths
STUDENT_NAME_MAX_LENGTH = 100
TEACHER_NAME_MAX_LENGTH = 100
GRADE_MAX_LENGTH = 20
STATUS_MAX_LENGTH = 20
EVENT_TYPE_MAX_LENGTH = 20
DISMISSAL_CODE_MAX_LENGTH = 8

# Pagination and limits
DASHBOARD_STUDENTS_PER_PAGE = 25
RECENT_EVENTS_LIMIT = 10
STUDENT_PICKUP_EVENTS_LIMIT = 20
BULK_IMPORT_ERROR_DISPLAY_LIMIT = 10

# Cache timeouts (in seconds)
DASHBOARD_CACHE_TIMEOUT = 60

# Rate limiting
PARENT_ARRIVAL_RATE_LIMIT = "20/m"

# Auto-generated dismissal codes start value
DISMISSAL_CODE_START_VALUE = 100
