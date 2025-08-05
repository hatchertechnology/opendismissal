import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.cache import cache
from dissmissal.models import Student, PickupEvent


class APIEndpointTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username="teststaff", email="test@school.edu", password="testpass123"
        )

        # Create test students
        self.student1 = Student.objects.create(
            name="Test Student 1", grade="3rd", teacher="Test Teacher", current_status="WAITING"
        )

        self.student2 = Student.objects.create(
            name="Test Student 2",
            grade="4th",
            teacher="Another Teacher",
            current_status="PARENT_ARRIVED",
        )

        self.student3 = Student.objects.create(
            name="Test Student 3", grade="5th", teacher="Third Teacher", current_status="PICKED_UP"
        )

        # Create a pickup event for student2
        PickupEvent.objects.create(
            student=self.student2,
            staff_member=self.staff_user,
            event_type="PARENT_ARRIVED",
            dismissal_code_used=self.student2.dismissal_code,
            ip_address="127.0.0.1",
        )

    def test_dashboard_status_api_requires_login(self):
        """Test that dashboard status API requires authentication"""
        url = reverse("dissmissal:dashboard_status_api")
        response = self.client.get(url)

        # Should redirect to login page
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_dashboard_status_api_authenticated(self):
        """Test dashboard status API with authenticated user"""
        self.client.login(username="teststaff", password="testpass123")
        url = reverse("dissmissal:dashboard_status_api")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Parse JSON response
        data = json.loads(response.content)

        # Check structure
        self.assertIn("students", data)
        self.assertIn("stats", data)

        # Check stats
        stats = data["stats"]
        self.assertEqual(stats["total_active"], 3)
        self.assertEqual(stats["waiting"], 1)
        self.assertEqual(stats["parent_arrived"], 1)
        self.assertEqual(stats["picked_up"], 1)

        # Check student data
        students = data["students"]
        self.assertEqual(len(students), 3)

        # Find our test students in the response
        student_names = [s["name"] for s in students]
        self.assertIn("Test Student 1", student_names)
        self.assertIn("Test Student 2", student_names)
        self.assertIn("Test Student 3", student_names)

    def test_dashboard_status_api_caching(self):
        """Test that dashboard status API uses caching"""
        self.client.login(username="teststaff", password="testpass123")
        url = reverse("dissmissal:dashboard_status_api")

        # Clear cache
        cache.clear()

        # First request should miss cache
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, 200)

        # Create a new student
        Student.objects.create(name="New Student", grade="1st", teacher="New Teacher")

        # Second request should hit cache (not see new student)
        response2 = self.client.get(url)
        self.assertEqual(response2.status_code, 200)

        data2 = json.loads(response2.content)
        self.assertEqual(data2["stats"]["total_active"], 3)  # Still 3, not 4

    def test_validate_dismissal_code_api_requires_login(self):
        """Test that code validation API requires authentication"""
        url = reverse("dissmissal:validate_code_api")
        response = self.client.post(url, {"code": "TEST123"})

        # Should redirect to login page
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_validate_dismissal_code_api_valid_code(self):
        """Test code validation API with valid code"""
        self.client.login(username="teststaff", password="testpass123")
        url = reverse("dissmissal:validate_code_api")

        response = self.client.post(url, {"code": self.student1.dismissal_code})
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertTrue(data["valid"])
        self.assertIn("student", data)

        student_data = data["student"]
        self.assertEqual(student_data["name"], "Test Student 1")
        self.assertEqual(student_data["grade"], "3rd")
        self.assertEqual(student_data["teacher"], "Test Teacher")
        self.assertEqual(student_data["current_status"], "WAITING")

    def test_validate_dismissal_code_api_invalid_code(self):
        """Test code validation API with invalid code"""
        self.client.login(username="teststaff", password="testpass123")
        url = reverse("dissmissal:validate_code_api")

        response = self.client.post(url, {"code": "INVALID"})
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertFalse(data["valid"])
        self.assertEqual(data["error"], "Invalid dismissal code")

    def test_validate_dismissal_code_api_empty_code(self):
        """Test code validation API with empty code"""
        self.client.login(username="teststaff", password="testpass123")
        url = reverse("dissmissal:validate_code_api")

        response = self.client.post(url, {"code": ""})
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertFalse(data["valid"])
        self.assertEqual(data["error"], "Dismissal code is required")

    def test_validate_dismissal_code_api_case_insensitive(self):
        """Test that code validation is case insensitive"""
        self.client.login(username="teststaff", password="testpass123")
        url = reverse("dissmissal:validate_code_api")

        # Test with lowercase version of code
        lowercase_code = self.student1.dismissal_code.lower()
        response = self.client.post(url, {"code": lowercase_code})
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertTrue(data["valid"])
        self.assertEqual(data["student"]["name"], "Test Student 1")

    def test_validate_dismissal_code_api_inactive_student(self):
        """Test that inactive students are not validated"""
        # Make student1 inactive
        self.student1.is_active = False
        self.student1.save()

        self.client.login(username="teststaff", password="testpass123")
        url = reverse("dissmissal:validate_code_api")

        response = self.client.post(url, {"code": self.student1.dismissal_code})
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertFalse(data["valid"])
        self.assertEqual(data["error"], "Invalid dismissal code")

    def test_validate_dismissal_code_api_only_post(self):
        """Test that code validation only accepts POST requests"""
        self.client.login(username="teststaff", password="testpass123")
        url = reverse("dissmissal:validate_code_api")

        # Try GET request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)  # Method not allowed

    def test_dashboard_status_api_only_get(self):
        """Test that dashboard status only accepts GET requests"""
        self.client.login(username="teststaff", password="testpass123")
        url = reverse("dissmissal:dashboard_status_api")

        # Try POST request
        response = self.client.post(url)
        self.assertEqual(response.status_code, 405)  # Method not allowed
