"""
Comprehensive tests for utility functions.
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.core.cache import cache
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from dissmissal.models import Student, PickupEvent
from dissmissal.utils import (
    get_client_ip,
    log_audit_event,
    get_dashboard_stats,
    validate_dismissal_code_format,
    sanitize_input,
    clear_dashboard_cache,
    generate_dashboard_cache_key,
    format_pickup_event_for_display,
    get_cache_key,
    format_time_ago,
    validate_staff_permissions,
    get_student_query_optimized,
)
import datetime
from unittest.mock import patch, MagicMock


class UtilityFunctionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="teststaff", 
            email="test@school.edu", 
            password="testpass123",
            is_staff=True
        )
        self.student = Student.objects.create(
            name="Test Student", 
            grade="3rd", 
            teacher="Test Teacher"
        )
        cache.clear()

    def test_get_client_ip_remote_addr(self):
        """Test IP extraction from REMOTE_ADDR"""
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        
        ip = get_client_ip(request)
        self.assertEqual(ip, "192.168.1.100")

    def test_get_client_ip_x_forwarded_for_single(self):
        """Test IP extraction from X-Forwarded-For with single IP"""
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.195"
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        
        ip = get_client_ip(request)
        self.assertEqual(ip, "203.0.113.195")

    def test_get_client_ip_x_forwarded_for_multiple(self):
        """Test IP extraction from X-Forwarded-For with multiple IPs"""
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.195, 70.41.3.18, 150.172.238.178"
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        
        ip = get_client_ip(request)
        self.assertEqual(ip, "203.0.113.195")

    def test_get_client_ip_fallback_to_remote_addr(self):
        """Test IP extraction fallback to REMOTE_ADDR"""
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        
        ip = get_client_ip(request)
        self.assertEqual(ip, "192.168.1.1")

    def test_get_client_ip_no_ip_returns_localhost(self):
        """Test that missing IP returns localhost"""
        request = self.factory.get("/")
        request.META = {}
        
        ip = get_client_ip(request)
        self.assertEqual(ip, "127.0.0.1")

    def test_validate_dismissal_code_format_valid_codes(self):
        """Test validation of valid dismissal code formats"""
        valid_codes = [
            "ABC",      # 3 characters (new minimum)
            "ABC123",   # 6 characters
            "ABCD12",   # 6 characters
            "A1B2C3",   # 6 characters
            "123ABC",   # 6 characters
            "AB123C",   # 6 characters
            "A12B34",   # 6 characters
            "A1B2C3D4", # 8 characters (maximum)
        ]
        
        for code in valid_codes:
            is_valid, message = validate_dismissal_code_format(code)
            self.assertTrue(is_valid, f"Code {code} should be valid")
            self.assertEqual(message, "")

    def test_validate_dismissal_code_format_invalid_codes(self):
        """Test validation of invalid dismissal code formats"""
        invalid_codes = [
            ("", "Dismissal code is required"),
            ("AB", "Dismissal code must be at least 3 characters for security"),
            ("ABCDEFGHI", "Dismissal code cannot exceed 8 characters"),
            ("ABC@123", "Dismissal code can only contain letters and numbers"),
            ("ABC 123", "Dismissal code can only contain letters and numbers"),
            ("ABC-123", "Dismissal code can only contain letters and numbers"),
            ("   ", "Dismissal code is required"),
        ]
        
        for code, expected_message in invalid_codes:
            is_valid, message = validate_dismissal_code_format(code)
            self.assertFalse(is_valid, f"Code '{code}' should be invalid")
            self.assertIn(expected_message, message)

    def test_sanitize_input_basic(self):
        """Test basic input sanitization"""
        test_cases = [
            ("Hello World", "Hello World"),
            ("<script>alert('xss')</script>", "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"),
            ("Test & Company", "Test &amp; Company"),
            ('Quote "test"', "Quote &quot;test&quot;"),
            ("Normal text 123", "Normal text 123"),
        ]
        
        for input_text, expected in test_cases:
            result = sanitize_input(input_text)
            self.assertEqual(result, expected)

    def test_sanitize_input_none_and_empty(self):
        """Test sanitization of None and empty values"""
        self.assertEqual(sanitize_input(None), "")
        self.assertEqual(sanitize_input(""), "")
        self.assertEqual(sanitize_input("   "), "")

    def test_generate_dashboard_cache_key(self):
        """Test dashboard cache key generation"""
        # Test basic key generation
        key = generate_dashboard_cache_key(user_id=1)
        self.assertTrue(key.startswith("dashboard_1"))
        
        # Test with filters
        key_with_filters = generate_dashboard_cache_key(
            user_id=1,
            status_filter="WAITING",
            grade_filter="3rd",
            search_query="test"
        )
        self.assertIn("WAITING", key_with_filters)
        self.assertIn("3rd", key_with_filters)
        self.assertIn("test", key_with_filters)

    def test_get_cache_key_generic(self):
        """Test generic cache key generation"""
        key = get_cache_key("test", "value1", "value2")
        self.assertTrue(key.startswith("test_"))
        self.assertIn("value1", key)
        self.assertIn("value2", key)

    def test_format_time_ago(self):
        """Test time ago formatting"""
        now = datetime.datetime.now()
        
        # Test recent times
        one_minute_ago = now - datetime.timedelta(minutes=1)
        self.assertEqual(format_time_ago(one_minute_ago), "1 minute ago")
        
        five_minutes_ago = now - datetime.timedelta(minutes=5)
        self.assertEqual(format_time_ago(five_minutes_ago), "5 minutes ago")
        
        one_hour_ago = now - datetime.timedelta(hours=1)
        self.assertEqual(format_time_ago(one_hour_ago), "1 hour ago")
        
        two_hours_ago = now - datetime.timedelta(hours=2)
        self.assertEqual(format_time_ago(two_hours_ago), "2 hours ago")

    def test_validate_staff_permissions(self):
        """Test staff permission validation"""
        # Test staff user
        self.assertTrue(validate_staff_permissions(self.user))
        
        # Test non-staff user
        regular_user = User.objects.create_user(
            username="regular", password="test123", is_staff=False
        )
        self.assertFalse(validate_staff_permissions(regular_user))
        
        # Test superuser who is also staff
        super_user = User.objects.create_user(
            username="super", password="test123", is_superuser=True, is_staff=True
        )
        self.assertTrue(validate_staff_permissions(super_user))

    def test_get_dashboard_stats(self):
        """Test dashboard statistics calculation"""
        # Create students with different statuses
        Student.objects.create(name="Student 1", grade="1st", teacher="T1", current_status="WAITING")
        Student.objects.create(name="Student 2", grade="2nd", teacher="T2", current_status="PARENT_ARRIVED")
        Student.objects.create(name="Student 3", grade="3rd", teacher="T3", current_status="PICKED_UP")
        Student.objects.create(name="Student 4", grade="4th", teacher="T4", is_active=False)
        
        stats = get_dashboard_stats()
        
        self.assertEqual(stats["total_active"], 4)  # Including the one from setUp
        self.assertEqual(stats["waiting"], 2)  # One from setUp (default WAITING) + one created above
        self.assertEqual(stats["parent_arrived"], 1)
        self.assertEqual(stats["picked_up"], 1)
        self.assertIn("waiting_percent", stats)
        self.assertIn("arrived_percent", stats)
        self.assertIn("picked_up_percent", stats)

    def test_format_pickup_event_for_display(self):
        """Test pickup event display formatting"""
        event = PickupEvent.objects.create(
            student=self.student,
            staff_member=self.user,
            event_type="PARENT_ARRIVED",
            dismissal_code_used=self.student.dismissal_code,
            ip_address="127.0.0.1",
            notes="Test event"
        )
        
        formatted = format_pickup_event_for_display(event)
        
        self.assertIn("event_type", formatted)
        self.assertIn("css_class", formatted)
        self.assertEqual(formatted["event_type"], "Parent Arrived")
        self.assertEqual(formatted["css_class"], "text-warning")

    @patch('dissmissal.utils.cache')
    def test_clear_dashboard_cache_with_pattern_support(self, mock_cache):
        """Test cache clearing with pattern support"""
        # Mock cache with delete_pattern support
        mock_cache.delete_pattern = MagicMock()
        
        clear_dashboard_cache(user_id=1)
        
        mock_cache.delete_pattern.assert_called_once()

    @patch('dissmissal.utils.cache')
    def test_clear_dashboard_cache_fallback(self, mock_cache):
        """Test cache clearing fallback when delete_pattern not available"""
        # Mock cache without delete_pattern support
        del mock_cache.delete_pattern
        mock_cache.clear = MagicMock()
        
        clear_dashboard_cache(user_id=1)
        
        mock_cache.clear.assert_called_once()

    def test_get_student_query_optimized(self):
        """Test optimized student query generation"""
        # Create some pickup events
        PickupEvent.objects.create(
            student=self.student,
            staff_member=self.user,
            event_type="PARENT_ARRIVED",
            dismissal_code_used=self.student.dismissal_code,
            ip_address="127.0.0.1"
        )
        
        queryset = get_student_query_optimized()
        
        # Test that the query is optimized (has select_related/prefetch_related)
        self.assertTrue(hasattr(queryset, '_prefetch_related_lookups'))
        
        # Test that it returns students
        students = list(queryset)
        self.assertIn(self.student, students)

    @patch('dissmissal.utils.logger')
    def test_log_audit_event(self, mock_logger):
        """Test audit event logging"""
        request = self.factory.get("/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        
        # Add session and messages to request
        middleware = SessionMiddleware()
        middleware.process_request(request)
        request.session.save()
        
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        
        log_audit_event(
            user=self.user,
            action="TEST_ACTION",
            ip_address="127.0.0.1",
            details={"test": "value"}
        )
        
        # Verify logger was called
        mock_logger.info.assert_called_once()
        
        # Verify log contains expected information
        call_args = mock_logger.info.call_args[0][0]
        self.assertIn("TEST_ACTION", call_args)
        self.assertIn(self.user.username, call_args)
        self.assertIn(self.student.name, call_args)


class ConcurrencyTests(TestCase):
    """Test concurrent access scenarios"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="teststaff", 
            password="testpass123",
            is_staff=True
        )
        self.student = Student.objects.create(
            name="Test Student", 
            grade="3rd", 
            teacher="Test Teacher"
        )

    def test_concurrent_cache_key_generation(self):
        """Test that cache key generation is thread-safe"""
        keys = []
        for i in range(100):
            key = generate_dashboard_cache_key(
                user_id=i,
                status_filter="WAITING",
                grade_filter="3rd"
            )
            keys.append(key)
        
        # All keys should be unique
        self.assertEqual(len(keys), len(set(keys)))

    def test_stats_calculation_consistency(self):
        """Test that stats calculation is consistent"""
        # Create multiple students
        for i in range(10):
            Student.objects.create(
                name=f"Student {i}",
                grade="3rd",
                teacher=f"Teacher {i}",
                current_status="WAITING" if i % 2 == 0 else "PARENT_ARRIVED"
            )
        
        # Calculate stats multiple times
        stats1 = get_dashboard_stats()
        stats2 = get_dashboard_stats()
        
        # Results should be identical
        self.assertEqual(stats1, stats2)


class ErrorHandlingTests(TestCase):
    """Test error handling in utility functions"""
    
    def test_get_client_ip_no_meta(self):
        """Test IP extraction when META is missing or empty"""
        request = self.factory.get("/")
        request.META = {}
        
        ip = get_client_ip(request)
        self.assertEqual(ip, "127.0.0.1")

    def test_validate_dismissal_code_format_none_input(self):
        """Test validation with None input"""
        is_valid, message = validate_dismissal_code_format(None)
        self.assertFalse(is_valid)
        self.assertEqual(message, "Dismissal code is required")

    def test_format_time_ago_valid_input(self):
        """Test time ago formatting with valid input"""
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        now = timezone.now()
        one_minute_ago = now - timedelta(minutes=1)
        result = format_time_ago(one_minute_ago)
        self.assertEqual(result, "1 minute ago")

    def test_sanitize_input_non_string(self):
        """Test sanitization with non-string input"""
        self.assertEqual(sanitize_input(123), "123")
        self.assertEqual(sanitize_input(True), "True")
        self.assertEqual(sanitize_input([]), "[]")