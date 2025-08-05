"""
Integration tests for complete OpenDismissal workflows.
"""

from django.test import TestCase, Client, TransactionTestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.cache import cache
from django.db import transaction
from dissmissal.models import Student, PickupEvent
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import threading
import time
from unittest.mock import patch


class CompleteWorkflowTests(TestCase):
    """Test complete dismissal workflows from start to finish"""
    
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username="staff1",
            password="testpass123",
            first_name="Staff",
            last_name="Member",
            is_staff=True
        )
        
        # Create multiple students
        self.students = []
        for i in range(5):
            student = Student.objects.create(
                name=f"Student {i+1}",
                grade=f"{i+1}st" if i < 3 else f"{i+1}th",
                teacher=f"Teacher {i+1}"
            )
            self.students.append(student)
        
        cache.clear()

    def test_complete_dismissal_workflow(self):
        """Test complete workflow: parent arrives -> student picked up"""
        self.client.login(username="staff1", password="testpass123")
        student = self.students[0]
        
        # Step 1: Verify initial state
        self.assertEqual(student.current_status, "WAITING")
        initial_events = PickupEvent.objects.count()
        
        # Step 2: Parent arrives
        response = self.client.post(reverse("dissmissal:parent_arrival"), {
            "dismissal_code": student.dismissal_code,
            "notes": "Parent at front door"
        })
        
        self.assertEqual(response.status_code, 302)  # Redirect on success
        
        # Verify parent arrival was recorded
        student.refresh_from_db()
        self.assertEqual(student.current_status, "PARENT_ARRIVED")
        self.assertEqual(PickupEvent.objects.count(), initial_events + 1)
        
        arrival_event = PickupEvent.objects.latest("timestamp")
        self.assertEqual(arrival_event.event_type, "PARENT_ARRIVED")
        self.assertEqual(arrival_event.student, student)
        self.assertEqual(arrival_event.staff_member, self.staff_user)
        
        # Step 3: Student pickup
        response = self.client.post(reverse("dissmissal:student_pickup"), {
            "student": student.id,
            "notes": "Student safely picked up"
        })
        
        self.assertEqual(response.status_code, 302)  # Redirect on success
        
        # Verify pickup was recorded
        student.refresh_from_db()
        self.assertEqual(student.current_status, "PICKED_UP")
        self.assertEqual(PickupEvent.objects.count(), initial_events + 2)
        
        pickup_event = PickupEvent.objects.latest("timestamp")
        self.assertEqual(pickup_event.event_type, "STUDENT_PICKED_UP")
        self.assertEqual(pickup_event.student, student)
        self.assertEqual(pickup_event.staff_member, self.staff_user)

    def test_multiple_students_workflow(self):
        """Test workflow with multiple students in sequence"""
        self.client.login(username="staff1", password="testpass123")
        
        for i, student in enumerate(self.students[:3]):
            with self.subTest(student=student.name):
                # Parent arrives
                response = self.client.post(reverse("dissmissal:parent_arrival"), {
                    "dismissal_code": student.dismissal_code,
                    "notes": f"Parent arrival {i+1}"
                })
                self.assertEqual(response.status_code, 302)
                
                # Verify status change
                student.refresh_from_db()
                self.assertEqual(student.current_status, "PARENT_ARRIVED")
                
                # Student pickup
                response = self.client.post(reverse("dissmissal:student_pickup"), {
                    "student": student.id,
                    "notes": f"Pickup {i+1}"
                })
                self.assertEqual(response.status_code, 302)
                
                # Verify final status
                student.refresh_from_db()
                self.assertEqual(student.current_status, "PICKED_UP")

    def test_dashboard_reflects_workflow_changes(self):
        """Test that dashboard updates reflect workflow changes"""
        self.client.login(username="staff1", password="testpass123")
        
        # Initial dashboard state
        response = self.client.get(reverse("dissmissal:dashboard"))
        self.assertEqual(response.status_code, 200)
        initial_stats = response.context["stats"]
        
        # Process one student
        student = self.students[0]
        self.client.post(reverse("dissmissal:parent_arrival"), {
            "dismissal_code": student.dismissal_code,
            "notes": "Test workflow"
        })
        
        # Dashboard should reflect changes (cache may delay this)
        cache.clear()  # Clear cache to see immediate changes
        response = self.client.get(reverse("dissmissal:dashboard"))
        updated_stats = response.context["stats"]
        
        # Stats should show the change
        self.assertEqual(
            updated_stats["parent_arrived"], 
            initial_stats["parent_arrived"] + 1
        )
        self.assertEqual(
            updated_stats["waiting"], 
            initial_stats["waiting"] - 1
        )

    def test_api_workflow_integration(self):
        """Test API endpoints work together in complete workflow"""
        self.client.login(username="staff1", password="testpass123")
        student = self.students[0]
        
        # Step 1: Validate dismissal code
        response = self.client.post(reverse("dissmissal:validate_code_api"), {
            "code": student.dismissal_code
        })
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["valid"])
        self.assertEqual(data["student"]["name"], student.name)
        
        # Step 2: Check dashboard status
        response = self.client.get(reverse("dissmissal:dashboard_status_api"))
        self.assertEqual(response.status_code, 200)
        status_data = json.loads(response.content)
        self.assertIn("students", status_data)
        self.assertIn("stats", status_data)
        
        # Step 3: Log parent arrival via form (simulate normal workflow)
        response = self.client.post(reverse("dissmissal:parent_arrival"), {
            "dismissal_code": student.dismissal_code,
            "notes": "API workflow test"
        })
        self.assertEqual(response.status_code, 302)
        
        # Step 4: Quick pickup via API
        response = self.client.post(
            reverse("dissmissal:quick_pickup_api"),
            data=json.dumps({
                "student_id": student.id,
                "notes": "Quick API pickup"
            }),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        api_data = json.loads(response.content)
        self.assertTrue(api_data["success"])
        
        # Verify final state
        student.refresh_from_db()
        self.assertEqual(student.current_status, "PICKED_UP")

    def test_error_recovery_workflow(self):
        """Test workflow recovery from error conditions"""
        self.client.login(username="staff1", password="testpass123")
        student = self.students[0]
        
        # Try invalid dismissal code first
        response = self.client.post(reverse("dissmissal:parent_arrival"), {
            "dismissal_code": "INVALID",
            "notes": "Should fail"
        })
        # Should stay on form with error
        self.assertEqual(response.status_code, 200)
        
        # Student status should be unchanged
        student.refresh_from_db()
        self.assertEqual(student.current_status, "WAITING")
        
        # Now use correct code - should work
        response = self.client.post(reverse("dissmissal:parent_arrival"), {
            "dismissal_code": student.dismissal_code,
            "notes": "Should succeed"
        })
        self.assertEqual(response.status_code, 302)
        
        # Status should now be updated
        student.refresh_from_db()
        self.assertEqual(student.current_status, "PARENT_ARRIVED")


class CacheIntegrationTests(TestCase):
    """Test cache behavior in integrated workflows"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="teststaff",
            password="testpass123",
            is_staff=True
        )
        self.student = Student.objects.create(
            name="Cache Test Student",
            grade="3rd",
            teacher="Test Teacher"
        )
        cache.clear()

    def test_cache_invalidation_on_status_change(self):
        """Test that cache is invalidated when student status changes"""
        self.client.login(username="teststaff", password="testpass123")
        
        # Load dashboard to populate cache
        response = self.client.get(reverse("dissmissal:dashboard"))
        self.assertEqual(response.status_code, 200)
        initial_stats = response.context["stats"]
        
        # Change student status
        response = self.client.post(reverse("dissmissal:parent_arrival"), {
            "dismissal_code": self.student.dismissal_code,
            "notes": "Cache invalidation test"
        })
        self.assertEqual(response.status_code, 302)
        
        # Load dashboard again - should reflect changes
        response = self.client.get(reverse("dissmissal:dashboard"))
        updated_stats = response.context["stats"]
        
        # Stats should be different (cache was invalidated)
        self.assertNotEqual(initial_stats["parent_arrived"], updated_stats["parent_arrived"])

    def test_api_cache_behavior(self):
        """Test API caching behavior"""
        self.client.login(username="teststaff", password="testpass123")
        
        # First API call
        response1 = self.client.get(reverse("dissmissal:dashboard_status_api"))
        self.assertEqual(response1.status_code, 200)
        data1 = json.loads(response1.content)
        
        # Change data
        self.client.post(reverse("dissmissal:parent_arrival"), {
            "dismissal_code": self.student.dismissal_code,
            "notes": "API cache test"
        })
        
        # Second API call - should show updated data
        response2 = self.client.get(reverse("dissmissal:dashboard_status_api"))
        self.assertEqual(response2.status_code, 200)
        data2 = json.loads(response2.content)
        
        # Data should be different (cache invalidated)
        self.assertNotEqual(data1["stats"]["parent_arrived"], data2["stats"]["parent_arrived"])


class ConcurrencyIntegrationTests(TransactionTestCase):
    """Test concurrent access scenarios using TransactionTestCase for real database transactions"""
    
    def setUp(self):
        self.staff_user1 = User.objects.create_user(
            username="staff1",
            password="testpass123",
            is_staff=True
        )
        self.staff_user2 = User.objects.create_user(
            username="staff2", 
            password="testpass123",
            is_staff=True
        )
        self.student = Student.objects.create(
            name="Concurrency Test Student",
            grade="3rd",
            teacher="Test Teacher"
        )

    def test_concurrent_parent_arrival_attempts(self):
        """Test concurrent attempts to log parent arrival for same student"""
        def attempt_parent_arrival(username):
            client = Client()
            client.login(username=username, password="testpass123")
            
            try:
                response = client.post(reverse("dissmissal:parent_arrival"), {
                    "dismissal_code": self.student.dismissal_code,
                    "notes": f"Arrival by {username}"
                })
                return response.status_code
            except Exception as e:
                return str(e)
        
        # Run concurrent requests
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(attempt_parent_arrival, "staff1"),
                executor.submit(attempt_parent_arrival, "staff2")
            ]
            
            results = [future.result() for future in as_completed(futures)]
        
        # One should succeed (302 redirect), one should get handled gracefully
        success_count = sum(1 for result in results if result == 302)
        
        # At least one should succeed
        self.assertGreaterEqual(success_count, 1)
        
        # Verify final state is consistent
        self.student.refresh_from_db()
        self.assertEqual(self.student.current_status, "PARENT_ARRIVED")
        
        # Should have exactly one parent arrival event
        arrival_events = PickupEvent.objects.filter(
            student=self.student,
            event_type="PARENT_ARRIVED"
        )
        self.assertEqual(arrival_events.count(), 1)

    def test_concurrent_dashboard_access(self):
        """Test concurrent dashboard access doesn't cause issues"""
        def access_dashboard(username):
            client = Client()
            client.login(username=username, password="testpass123")
            
            try:
                response = client.get(reverse("dissmissal:dashboard"))
                return response.status_code
            except Exception as e:
                return str(e)
        
        # Run concurrent dashboard requests
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(access_dashboard, f"staff{i}")
                for i in [1, 2, 1]  # staff1 accesses twice, staff2 once
            ]
            
            results = [future.result() for future in as_completed(futures)]
        
        # All should succeed or redirect appropriately
        for result in results:
            self.assertIn(result, [200, 302])  # Success or redirect


class FormIntegrationTests(TestCase):
    """Test form integration with views and models"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="teststaff",
            password="testpass123", 
            is_staff=True
        )

    def test_add_student_form_integration(self):
        """Test complete add student workflow"""
        self.client.login(username="teststaff", password="testpass123")
        
        initial_count = Student.objects.count()
        
        # Submit form
        response = self.client.post(reverse("dissmissal:add_student"), {
            "name": "integration test student",
            "grade": "5th",
            "teacher": "integration teacher"
        })
        
        # Should redirect on success
        self.assertEqual(response.status_code, 302)
        
        # Student should be created
        self.assertEqual(Student.objects.count(), initial_count + 1)
        
        # Student should have proper formatting
        new_student = Student.objects.latest("id")
        self.assertEqual(new_student.name, "Integration Test Student")
        self.assertEqual(new_student.teacher, "Integration Teacher")
        self.assertEqual(new_student.grade, "5th")
        self.assertTrue(new_student.is_active)
        self.assertIsNotNone(new_student.dismissal_code)
        self.assertEqual(len(new_student.dismissal_code), 6)

    def test_form_validation_error_handling(self):
        """Test form validation error display"""
        self.client.login(username="teststaff", password="testpass123")
        
        # Submit invalid form
        response = self.client.post(reverse("dissmissal:add_student"), {
            "name": "",  # Required field
            "grade": "5th",
            "teacher": "Test Teacher"
        })
        
        # Should stay on form page
        self.assertEqual(response.status_code, 200)
        
        # Should contain form errors
        self.assertContains(response, "This field is required")

    def test_parent_arrival_form_with_notes(self):
        """Test parent arrival form with optional notes"""
        student = Student.objects.create(
            name="Notes Test Student",
            grade="3rd", 
            teacher="Test Teacher"
        )
        
        self.client.login(username="teststaff", password="testpass123")
        
        # Submit with notes
        response = self.client.post(reverse("dissmissal:parent_arrival"), {
            "dismissal_code": student.dismissal_code,
            "notes": "Parent mentioned running late"
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify notes were saved
        event = PickupEvent.objects.latest("timestamp")
        self.assertEqual(event.notes, "Parent mentioned running late")


class PerformanceIntegrationTests(TestCase):
    """Test performance-related integration scenarios"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="teststaff",
            password="testpass123",
            is_staff=True
        )
        
        # Create many students for performance testing
        self.students = []
        for i in range(50):
            student = Student.objects.create(
                name=f"Performance Student {i:03d}",
                grade=f"{(i % 8) + 1}{'st' if (i % 8) == 0 else ('nd' if (i % 8) == 1 else ('rd' if (i % 8) == 2 else 'th'))}",
                teacher=f"Teacher {i % 10}"
            )
            self.students.append(student)
            
            # Create some pickup events
            if i % 3 == 0:
                PickupEvent.objects.create(
                    student=student,
                    staff_member=self.user,
                    event_type="PARENT_ARRIVED",
                    dismissal_code_used=student.dismissal_code,
                    ip_address="127.0.0.1"
                )
                student.current_status = "PARENT_ARRIVED"
                student.save()

    def test_dashboard_performance_with_many_students(self):
        """Test dashboard performance with large dataset"""
        self.client.login(username="teststaff", password="testpass123")
        
        # Time the dashboard load
        start_time = time.time()
        response = self.client.get(reverse("dissmissal:dashboard"))
        load_time = time.time() - start_time
        
        self.assertEqual(response.status_code, 200)
        
        # Should load in reasonable time (less than 2 seconds)
        self.assertLess(load_time, 2.0)
        
        # Should contain expected data
        self.assertContains(response, "Performance Student")
        
        # Check pagination is working
        students_on_page = response.context["students"]
        self.assertLessEqual(len(students_on_page), 25)  # Page size limit

    def test_api_performance_with_many_students(self):
        """Test API performance with large dataset"""
        self.client.login(username="teststaff", password="testpass123")
        
        # Time the API call
        start_time = time.time()
        response = self.client.get(reverse("dissmissal:dashboard_status_api"))
        api_time = time.time() - start_time
        
        self.assertEqual(response.status_code, 200)
        
        # Should respond quickly (less than 1 second)
        self.assertLess(api_time, 1.0)
        
        # Should contain all students in API response
        data = json.loads(response.content)
        self.assertIn("students", data)
        self.assertIn("stats", data)

    def test_search_performance(self):
        """Test search functionality performance"""
        self.client.login(username="teststaff", password="testpass123")
        
        # Search for specific students
        search_terms = ["Student 001", "Teacher 5", "3rd"]
        
        for term in search_terms:
            with self.subTest(search_term=term):
                start_time = time.time()
                response = self.client.get(
                    reverse("dissmissal:dashboard"),
                    {"search": term}
                )
                search_time = time.time() - start_time
                
                self.assertEqual(response.status_code, 200)
                self.assertLess(search_time, 1.0)
                
                # Should return relevant results
                if "Student" in term:
                    self.assertContains(response, term)


class ErrorHandlingIntegrationTests(TestCase):
    """Test error handling in integrated scenarios"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="teststaff",
            password="testpass123",
            is_staff=True
        )

    def test_graceful_handling_of_missing_student(self):
        """Test handling when student is deleted mid-workflow"""
        student = Student.objects.create(
            name="Temporary Student",
            grade="3rd",
            teacher="Test Teacher"
        )
        
        self.client.login(username="teststaff", password="testpass123")
        
        # Log parent arrival
        response = self.client.post(reverse("dissmissal:parent_arrival"), {
            "dismissal_code": student.dismissal_code,
            "notes": "Test deletion scenario"
        })
        self.assertEqual(response.status_code, 302)
        
        # Delete student (simulate data integrity issue)
        student_id = student.id
        student.delete()
        
        # Try to pick up deleted student
        response = self.client.post(reverse("dissmissal:student_pickup"), {
            "student": student_id,
            "notes": "Should fail gracefully"
        })
        
        # Should handle error gracefully (not crash)
        self.assertNotEqual(response.status_code, 500)

    def test_database_error_recovery(self):
        """Test recovery from database-related errors"""
        self.client.login(username="teststaff", password="testpass123")
        
        # Try with malformed student ID
        response = self.client.post(reverse("dissmissal:student_pickup"), {
            "student": "invalid_id",
            "notes": "Should handle invalid ID"
        })
        
        # Should handle gracefully
        self.assertNotEqual(response.status_code, 500)

    def test_cache_failure_fallback(self):
        """Test behavior when cache fails"""
        self.client.login(username="teststaff", password="testpass123")
        
        with patch('django.core.cache.cache.get', side_effect=Exception("Cache error")):
            # Dashboard should still work without cache
            response = self.client.get(reverse("dissmissal:dashboard"))
            self.assertEqual(response.status_code, 200)