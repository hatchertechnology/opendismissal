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
