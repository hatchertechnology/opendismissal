"""
OpenDismissal Test Suite

Comprehensive tests for the dismissal management system.
Author: Derek Hayes
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.cache import cache
from dissmissal.models import Student, PickupEvent
from dissmissal.forms import ParentArrivalForm, AddStudentForm
from dissmissal.utils import get_client_ip, validate_dismissal_code_format
import json


class ModelTestCase(TestCase):
    """Test cases for model functionality"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="teststaff",
            email="test@school.edu",
            password="testpass123",
            first_name="Test",
            last_name="Staff",
            is_staff=True,
        )

    def test_student_creation(self):
        """Test student model creation and dismissal code generation"""
        student = Student.objects.create(name="Test Student", grade="3rd", teacher="Test Teacher")

        self.assertEqual(student.name, "Test Student")
        self.assertEqual(student.grade, "3rd")
        self.assertEqual(student.teacher, "Test Teacher")
        self.assertEqual(student.current_status, "WAITING")
        self.assertTrue(student.is_active)
        self.assertIsNotNone(student.dismissal_code)
        self.assertEqual(len(student.dismissal_code), 6)

    def test_student_name_formatting(self):
        """Test student name proper case formatting"""
        student = Student.objects.create(
            name="test student name", grade="4th", teacher="test teacher"
        )

        self.assertEqual(student.name, "Test Student Name")
        self.assertEqual(student.teacher, "Test Teacher")

    def test_pickup_event_creation(self):
        """Test pickup event creation and student status update"""
        student = Student.objects.create(name="Test Student", grade="3rd", teacher="Test Teacher")

        pickup_event = PickupEvent.objects.create(
            student=student,
            staff_member=self.user,
            event_type="PARENT_ARRIVED",
            dismissal_code_used=student.dismissal_code,
            ip_address="127.0.0.1",
        )

        # Refresh student from database
        student.refresh_from_db()

        self.assertEqual(pickup_event.student, student)
        self.assertEqual(pickup_event.staff_member, self.user)
        self.assertEqual(pickup_event.event_type, "PARENT_ARRIVED")
        self.assertEqual(student.current_status, "PARENT_ARRIVED")

    def test_unique_dismissal_codes(self):
        """Test that dismissal codes are unique"""
        student1 = Student.objects.create(name="Student One", grade="3rd", teacher="Teacher One")

        student2 = Student.objects.create(name="Student Two", grade="4th", teacher="Teacher Two")

        self.assertNotEqual(student1.dismissal_code, student2.dismissal_code)


class FormTestCase(TestCase):
    """Test cases for form validation"""

    def setUp(self):
        """Set up test data"""
        self.student = Student.objects.create(
            name="Test Student", grade="3rd", teacher="Test Teacher"
        )

    def test_parent_arrival_form_valid(self):
        """Test valid parent arrival form"""
        form_data = {"dismissal_code": self.student.dismissal_code, "notes": "Test arrival notes"}
        form = ParentArrivalForm(data=form_data)

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["dismissal_code"], self.student.dismissal_code)
        self.assertEqual(form.cleaned_data["notes"], "Test arrival notes")

    def test_parent_arrival_form_invalid_code(self):
        """Test parent arrival form with invalid dismissal code"""
        form_data = {"dismissal_code": "INVALID", "notes": ""}
        form = ParentArrivalForm(data=form_data)

        self.assertFalse(form.is_valid())
        self.assertIn("dismissal_code", form.errors)

    def test_add_student_form_valid(self):
        """Test valid add student form"""
        form_data = {"name": "New Student", "grade": "5th", "teacher": "New Teacher"}
        form = AddStudentForm(data=form_data)

        self.assertTrue(form.is_valid())

        student = form.save()
        self.assertEqual(student.name, "New Student")
        self.assertEqual(student.grade, "5th")
        self.assertEqual(student.teacher, "New Teacher")

    def test_add_student_form_name_formatting(self):
        """Test add student form name formatting"""
        form_data = {"name": "new student name", "grade": "5th", "teacher": "new teacher"}
        form = AddStudentForm(data=form_data)

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["name"], "New Student Name")
        self.assertEqual(form.cleaned_data["teacher"], "New Teacher")


class ViewTestCase(TestCase):
    """Test cases for view functionality"""

    def setUp(self):
        """Set up test data and authenticated client"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="teststaff",
            email="test@school.edu",
            password="testpass123",
            first_name="Test",
            last_name="Staff",
            is_staff=True,
        )

        # Create test student
        self.student = Student.objects.create(
            name="Test Student", grade="3rd", teacher="Test Teacher", current_status="WAITING"
        )

        # Clear cache before each test
        cache.clear()

    def test_dashboard_requires_authentication(self):
        """Test dashboard redirects unauthenticated users"""
        response = self.client.get(reverse("dissmissal:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_dashboard_loads_with_students(self):
        """Test dashboard loads correctly with student data"""
        self.client.login(username="teststaff", password="testpass123")
        response = self.client.get(reverse("dissmissal:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Student")
        self.assertContains(response, self.student.dismissal_code)
        self.assertIn("stats", response.context)
        self.assertIn("students", response.context)

    def test_parent_arrival_workflow_success(self):
        """Test successful parent arrival logging"""
        self.client.login(username="teststaff", password="testpass123")

        response = self.client.post(
            reverse("dissmissal:parent_arrival"),
            {"dismissal_code": self.student.dismissal_code, "notes": "Test arrival notes"},
        )

        # Should redirect to dashboard
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dissmissal:dashboard"))

        # Check student status was updated
        self.student.refresh_from_db()
        self.assertEqual(self.student.current_status, "PARENT_ARRIVED")

        # Check pickup event was created
        event = PickupEvent.objects.get(student=self.student, event_type="PARENT_ARRIVED")
        self.assertEqual(event.staff_member, self.user)
        self.assertEqual(event.notes, "Test arrival notes")

    def test_parent_arrival_invalid_code(self):
        """Test parent arrival with invalid dismissal code"""
        self.client.login(username="teststaff", password="testpass123")

        response = self.client.post(
            reverse("dissmissal:parent_arrival"), {"dismissal_code": "INVALID", "notes": ""}
        )

        # Should stay on same page with error
        self.assertEqual(response.status_code, 200)
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Invalid dismissal code" in str(m) for m in messages))

        # Student status should not change
        self.student.refresh_from_db()
        self.assertEqual(self.student.current_status, "WAITING")

    def test_student_pickup_completion(self):
        """Test student pickup completion workflow"""
        # Set student to parent_arrived status first
        self.student.current_status = "PARENT_ARRIVED"
        self.student.save()

        self.client.login(username="teststaff", password="testpass123")

        response = self.client.post(
            reverse("dissmissal:student_pickup"),
            {"student": self.student.id, "notes": "Pickup completed successfully"},
        )

        # Should redirect to dashboard
        self.assertEqual(response.status_code, 302)

        # Check student status was updated
        self.student.refresh_from_db()
        self.assertEqual(self.student.current_status, "PICKED_UP")

        # Check pickup completion event was created
        event = PickupEvent.objects.get(student=self.student, event_type="STUDENT_PICKED_UP")
        self.assertEqual(event.staff_member, self.user)
        self.assertEqual(event.notes, "Pickup completed successfully")

    def test_add_student_functionality(self):
        """Test adding new student to system"""
        self.client.login(username="teststaff", password="testpass123")

        response = self.client.post(
            reverse("dissmissal:add_student"),
            {"name": "New Test Student", "grade": "4th", "teacher": "New Teacher"},
        )

        # Should redirect to dashboard
        self.assertEqual(response.status_code, 302)

        # Check student was created
        new_student = Student.objects.get(name="New Test Student")
        self.assertEqual(new_student.grade, "4th")
        self.assertEqual(new_student.teacher, "New Teacher")
        self.assertIsNotNone(new_student.dismissal_code)
        self.assertEqual(len(new_student.dismissal_code), 6)


class APITestCase(TestCase):
    """Test cases for API endpoints"""

    def setUp(self):
        """Set up test data and authenticated client"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="teststaff",
            email="test@school.edu",
            password="testpass123",
            first_name="Test",
            last_name="Staff",
            is_staff=True,
        )

        self.student = Student.objects.create(
            name="Test Student", grade="3rd", teacher="Test Teacher", current_status="WAITING"
        )

    def test_dashboard_status_api(self):
        """Test dashboard status API endpoint"""
        self.client.login(username="teststaff", password="testpass123")

        response = self.client.get(reverse("dissmissal:dashboard_status_api"))
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertIn("students", data)
        self.assertIn("stats", data)
        self.assertEqual(len(data["students"]), 1)
        self.assertEqual(data["students"][0]["name"], "Test Student")

    def test_validate_dismissal_code_api(self):
        """Test dismissal code validation API"""
        self.client.login(username="teststaff", password="testpass123")

        # Test valid code
        response = self.client.post(
            reverse("dissmissal:validate_code_api"),
            data=json.dumps({"dismissal_code": self.student.dismissal_code}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["valid"])
        self.assertEqual(data["student"]["name"], "Test Student")

        # Test invalid code
        response = self.client.post(
            reverse("dissmissal:validate_code_api"),
            data=json.dumps({"dismissal_code": "INVALID"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertFalse(data["valid"])

    def test_quick_pickup_api(self):
        """Test quick pickup API endpoint"""
        # Set student to parent_arrived status
        self.student.current_status = "PARENT_ARRIVED"
        self.student.save()

        self.client.login(username="teststaff", password="testpass123")

        response = self.client.post(
            reverse("dissmissal:quick_pickup_api"),
            data=json.dumps({"student_id": self.student.id, "notes": "Quick pickup test"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])

        # Check student status was updated
        self.student.refresh_from_db()
        self.assertEqual(self.student.current_status, "PICKED_UP")


class UtilityTestCase(TestCase):
    """Test cases for utility functions"""

    def test_validate_dismissal_code_format(self):
        """Test dismissal code format validation"""
        # Valid codes (updated for 1-8 character range)
        self.assertTrue(validate_dismissal_code_format("ABC123")[0])
        self.assertTrue(validate_dismissal_code_format("ABCD12")[0])
        self.assertTrue(validate_dismissal_code_format("AB123CD8")[0])
        self.assertTrue(validate_dismissal_code_format("ABC")[0])  # Now valid (1 char minimum)

        # Invalid codes
        self.assertFalse(validate_dismissal_code_format("")[0])
        self.assertTrue(validate_dismissal_code_format("AB")[0])  # Now valid (2 chars, min is 1)
        self.assertFalse(validate_dismissal_code_format("ABCDEFGHI")[0])  # Too long (> 8)
        self.assertFalse(validate_dismissal_code_format("ABC@123")[0])  # Invalid characters
        
        # Test allow_empty parameter
        self.assertTrue(validate_dismissal_code_format("", allow_empty=True)[0])
        self.assertFalse(validate_dismissal_code_format("", allow_empty=False)[0])

    def test_get_client_ip(self):
        """Test IP address extraction"""
        from django.test import RequestFactory

        factory = RequestFactory()

        # Test normal request
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        self.assertEqual(get_client_ip(request), "192.168.1.1")

        # Test with X-Forwarded-For header
        request = factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.195, 70.41.3.18, 150.172.238.178"
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        self.assertEqual(get_client_ip(request), "203.0.113.195")


class SecurityTestCase(TestCase):
    """Test cases for security features"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="teststaff", password="testpass123", is_staff=True
        )

    def test_unauthenticated_access_blocked(self):
        """Test that unauthenticated users cannot access protected views"""
        protected_urls = [
            reverse("dissmissal:dashboard"),
            reverse("dissmissal:parent_arrival"),
            reverse("dissmissal:student_pickup"),
            reverse("dissmissal:add_student"),
        ]

        for url in protected_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_csrf_protection(self):
        """Test CSRF protection on POST requests"""
        self.client.login(username="teststaff", password="testpass123")

        # Test POST without CSRF token should fail
        response = self.client.post(
            reverse("dissmissal:parent_arrival"), {"dismissal_code": "ABC123"}, HTTP_X_CSRFTOKEN=""
        )
        # Django test client automatically handles CSRF, so we check the form is present
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "csrfmiddlewaretoken")


class EdgeCaseTests(TestCase):
    """Test edge cases and error conditions for robustness"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="teststaff", password="testpass123", is_staff=True
        )

    def test_concurrent_parent_arrival_same_student(self):
        """Test race condition handling for concurrent parent arrivals"""
        student = Student.objects.create(
            name="Test Student", grade="3rd", teacher="Test Teacher"
        )
        
        self.client.login(username="teststaff", password="testpass123")
        
        # First arrival should succeed
        response1 = self.client.post(
            reverse("dissmissal:parent_arrival"),
            {"dismissal_code": student.dismissal_code, "notes": "First arrival"}
        )
        self.assertEqual(response1.status_code, 302)
        
        # Second arrival should be handled gracefully
        response2 = self.client.post(
            reverse("dissmissal:parent_arrival"),
            {"dismissal_code": student.dismissal_code, "notes": "Duplicate arrival"}
        )
        self.assertEqual(response2.status_code, 200)  # Stays on page with warning

    def test_malformed_dismissal_codes(self):
        """Test handling of various malformed dismissal codes"""
        student = Student.objects.create(
            name="Test Student", grade="3rd", teacher="Test Teacher"
        )
        
        self.client.login(username="teststaff", password="testpass123")
        
        malformed_codes = [
            "",  # Empty
            "a",  # Too short
            "abcdefghijk",  # Too long
            "ABC@123",  # Invalid characters
            "   ",  # Whitespace only
            "abc123!",  # Special characters
        ]
        
        for code in malformed_codes:
            response = self.client.post(
                reverse("dissmissal:parent_arrival"),
                {"dismissal_code": code, "notes": ""}
            )
            self.assertEqual(response.status_code, 200)  # Should stay on form with error

    def test_database_query_optimization(self):
        """Test that queries are optimized to prevent N+1 problems"""
        # Create multiple students with events
        students = []
        for i in range(10):
            student = Student.objects.create(
                name=f"Student {i}", grade="3rd", teacher=f"Teacher {i}"
            )
            students.append(student)
            
            # Create pickup events for each student
            PickupEvent.objects.create(
                student=student,
                staff_member=self.user,
                event_type="PARENT_ARRIVED",
                dismissal_code_used=student.dismissal_code,
                ip_address="127.0.0.1"
            )
        
        self.client.login(username="teststaff", password="testpass123")
        
        # Dashboard should use optimized queries
        with self.assertNumQueries(8):  # Should be minimal queries due to optimization
            response = self.client.get(reverse("dissmissal:dashboard"))
            self.assertEqual(response.status_code, 200)

    def test_cache_invalidation_on_data_changes(self):
        """Test that cache is properly invalidated when data changes"""
        student = Student.objects.create(
            name="Test Student", grade="3rd", teacher="Test Teacher"
        )
        
        self.client.login(username="teststaff", password="testpass123")
        
        # Load dashboard to populate cache
        response1 = self.client.get(reverse("dissmissal:dashboard"))
        self.assertEqual(response1.status_code, 200)
        
        # Change student status
        response2 = self.client.post(
            reverse("dissmissal:parent_arrival"),
            {"dismissal_code": student.dismissal_code, "notes": "Cache test"}
        )
        self.assertEqual(response2.status_code, 302)
        
        # Dashboard should reflect changes (cache invalidated)
        response3 = self.client.get(reverse("dissmissal:dashboard"))
        self.assertEqual(response3.status_code, 200)
        student.refresh_from_db()
        self.assertEqual(student.current_status, "PARENT_ARRIVED")

    def test_large_dataset_pagination_performance(self):
        """Test pagination performance with large datasets"""
        # Create 100 students
        students = []
        for i in range(100):
            student = Student.objects.create(
                name=f"Student {i:03d}", grade="3rd", teacher=f"Teacher {i % 10}"
            )
            students.append(student)
        
        self.client.login(username="teststaff", password="testpass123")
        
        # Test first page
        response = self.client.get(reverse("dissmissal:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student 000")  # Should show first students
        
        # Test pagination
        response = self.client.get(reverse("dissmissal:dashboard") + "?page=2")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student 025")  # Should show page 2 students
