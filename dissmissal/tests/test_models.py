from django.test import TestCase
from django.contrib.auth.models import User
from dissmissal.models import Student, PickupEvent


class StudentModelTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="teststaff", email="test@school.edu", password="testpass123"
        )

    def test_student_creation_with_auto_code_generation(self):
        """Test student creation with automatic dismissal code generation"""
        student = Student.objects.create(name="Test Student", grade="3rd", teacher="Test Teacher")

        self.assertIsNotNone(student.dismissal_code)
        self.assertEqual(len(student.dismissal_code), 6)
        self.assertTrue(student.dismissal_code.isalnum())
        self.assertTrue(student.dismissal_code.isupper())

    def test_dismissal_code_uniqueness(self):
        """Test that dismissal codes are unique across students"""
        student1 = Student.objects.create(name="Student 1", grade="1st", teacher="Teacher 1")
        student2 = Student.objects.create(name="Student 2", grade="2nd", teacher="Teacher 2")

        self.assertNotEqual(student1.dismissal_code, student2.dismissal_code)

    def test_student_default_status(self):
        """Test that students are created with WAITING status by default"""
        student = Student.objects.create(name="Test Student", grade="3rd", teacher="Test Teacher")

        self.assertEqual(student.current_status, "WAITING")
        self.assertTrue(student.is_active)

    def test_student_str_representation(self):
        """Test student string representation"""
        student = Student.objects.create(name="Test Student", grade="3rd", teacher="Test Teacher")

        expected = f"Test Student ({student.dismissal_code}) - {student.get_current_status_display()}"
        self.assertEqual(str(student), expected)

    def test_pickup_event_creation_and_status_update(self):
        """Test pickup event creation updates student status"""
        student = Student.objects.create(name="Test Student", grade="3rd", teacher="Test Teacher")

        # Verify initial status
        self.assertEqual(student.current_status, "WAITING")

        # Create parent arrival event
        PickupEvent.objects.create(
            student=student,
            staff_member=self.staff_user,
            event_type="PARENT_ARRIVED",
            dismissal_code_used=student.dismissal_code,
            ip_address="127.0.0.1",
        )

        # Verify status was updated
        student.refresh_from_db()
        self.assertEqual(student.current_status, "PARENT_ARRIVED")

        # Create pickup completion event
        PickupEvent.objects.create(
            student=student,
            staff_member=self.staff_user,
            event_type="STUDENT_PICKED_UP",
            dismissal_code_used=student.dismissal_code,
            ip_address="127.0.0.1",
        )

        # Verify final status
        student.refresh_from_db()
        self.assertEqual(student.current_status, "PICKED_UP")

    def test_pickup_event_cancelled_status(self):
        """Test that cancelled events reset student to WAITING"""
        student = Student.objects.create(
            name="Test Student",
            grade="3rd",
            teacher="Test Teacher",
            current_status="PARENT_ARRIVED",
        )

        # Create cancelled event
        PickupEvent.objects.create(
            student=student,
            staff_member=self.staff_user,
            event_type="CANCELLED",
            dismissal_code_used=student.dismissal_code,
            ip_address="127.0.0.1",
            notes="Pickup cancelled",
        )

        # Verify status was reset
        student.refresh_from_db()
        self.assertEqual(student.current_status, "WAITING")

    def test_student_manager_methods(self):
        """Test custom manager methods work correctly"""
        # Create test students with different statuses
        waiting_student = Student.objects.create(
            name="Waiting Student", grade="1st", teacher="Teacher 1", current_status="WAITING"
        )

        arrived_student = Student.objects.create(
            name="Arrived Student",
            grade="2nd",
            teacher="Teacher 2",
            current_status="PARENT_ARRIVED",
        )

        picked_up_student = Student.objects.create(
            name="Picked Up Student", grade="3rd", teacher="Teacher 3", current_status="PICKED_UP"
        )

        inactive_student = Student.objects.create(
            name="Inactive Student", grade="4th", teacher="Teacher 4", is_active=False
        )

        # Test waiting_for_pickup method
        waiting_students = Student.objects.waiting_for_pickup()
        waiting_students_list = list(waiting_students)
        self.assertEqual(waiting_students.count(), 2)  # WAITING + PARENT_ARRIVED
        self.assertIn(waiting_student, waiting_students_list)
        self.assertIn(arrived_student, waiting_students_list)
        self.assertNotIn(picked_up_student, waiting_students_list)
        self.assertNotIn(inactive_student, waiting_students_list)

        # Test by_grade method
        first_grade_students = Student.objects.by_grade("1st")
        first_grade_students_list = list(first_grade_students)
        self.assertEqual(first_grade_students.count(), 1)
        self.assertIn(waiting_student, first_grade_students_list)

    def test_get_latest_event(self):
        """Test getting the latest event for a student"""
        student = Student.objects.create(name="Test Student", grade="3rd", teacher="Test Teacher")

        # Initially no events
        self.assertIsNone(student.get_latest_event())

        # Create first event
        event1 = PickupEvent.objects.create(
            student=student,
            staff_member=self.staff_user,
            event_type="PARENT_ARRIVED",
            dismissal_code_used=student.dismissal_code,
            ip_address="127.0.0.1",
        )

        self.assertEqual(student.get_latest_event(), event1)

        # Create second event
        event2 = PickupEvent.objects.create(
            student=student,
            staff_member=self.staff_user,
            event_type="STUDENT_PICKED_UP",
            dismissal_code_used=student.dismissal_code,
            ip_address="127.0.0.1",
        )

        # Latest should be the second event
        self.assertEqual(student.get_latest_event(), event2)


class PickupEventModelTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="teststaff", email="test@school.edu", password="testpass123"
        )
        self.student = Student.objects.create(
            name="Test Student", grade="3rd", teacher="Test Teacher"
        )

    def test_pickup_event_creation(self):
        """Test basic pickup event creation"""
        event = PickupEvent.objects.create(
            student=self.student,
            staff_member=self.staff_user,
            event_type="PARENT_ARRIVED",
            dismissal_code_used=self.student.dismissal_code,
            ip_address="127.0.0.1",
            notes="Test event",
        )

        self.assertEqual(event.student, self.student)
        self.assertEqual(event.staff_member, self.staff_user)
        self.assertEqual(event.event_type, "PARENT_ARRIVED")
        self.assertEqual(event.dismissal_code_used, self.student.dismissal_code)
        self.assertEqual(event.ip_address, "127.0.0.1")
        self.assertEqual(event.notes, "Test event")

    def test_pickup_event_str_representation(self):
        """Test pickup event string representation"""
        self.staff_user.first_name = "Test"
        self.staff_user.last_name = "Staff"
        self.staff_user.save()

        event = PickupEvent.objects.create(
            student=self.student,
            staff_member=self.staff_user,
            event_type="PARENT_ARRIVED",
            dismissal_code_used=self.student.dismissal_code,
            ip_address="127.0.0.1",
        )

        expected = f"{self.student.name} - Parent Arrived by Test Staff"
        self.assertEqual(str(event), expected)

    def test_pickup_event_ordering(self):
        """Test that pickup events are ordered by timestamp descending"""
        # Create two events
        event1 = PickupEvent.objects.create(
            student=self.student,
            staff_member=self.staff_user,
            event_type="PARENT_ARRIVED",
            dismissal_code_used=self.student.dismissal_code,
            ip_address="127.0.0.1",
        )

        event2 = PickupEvent.objects.create(
            student=self.student,
            staff_member=self.staff_user,
            event_type="STUDENT_PICKED_UP",
            dismissal_code_used=self.student.dismissal_code,
            ip_address="127.0.0.1",
        )

        # Get all events - should be ordered with most recent first
        events = list(PickupEvent.objects.all())
        self.assertEqual(events[0], event2)  # Most recent first
        self.assertEqual(events[1], event1)

    def test_generate_dismissal_code_uniqueness(self):
        """Test that generate_dismissal_code produces unique codes"""
        codes = set()
        for _ in range(100):  # Generate 100 codes
            code = Student.generate_dismissal_code()
            self.assertNotIn(code, codes, "Generated duplicate code")
            codes.add(code)
            self.assertEqual(len(code), 6)
            self.assertTrue(code.isalnum())
            self.assertTrue(code.isupper())
