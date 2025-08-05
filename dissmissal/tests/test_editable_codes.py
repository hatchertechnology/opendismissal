"""
Tests for editable dismissal codes functionality.

Tests core requirements:
- FR-1: Admin can manually enter codes (3-8 characters, alphanumeric)
- FR-2: Admin can edit existing student dismissal codes
- FR-3: 3-character minimum for security
- FR-4: Optional auto-generation when field blank
- FR-5: Code changes logged in audit trail
- FR-6: Bulk CSV import functionality
- FR-7: Admin interface shows codes in list/search
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from unittest.mock import patch, MagicMock
import tempfile
import os
import csv

from dissmissal.models import Student, validate_dismissal_code_format
from dissmissal.admin import StudentAdmin
from dissmissal.utils import log_audit_event


class EditableDismissalCodesModelTests(TestCase):
    """Test model functionality for editable dismissal codes"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="teststaff",
            email="test@school.edu", 
            password="testpass123",
            is_staff=True
        )

    def test_manual_code_entry_valid(self):
        """FR-1: Test valid 3-8 character codes are accepted"""
        valid_codes = ["101", "ABC", "A1B", "205", "ABC123", "A1B2C3D4"]
        
        for code in valid_codes:
            with self.subTest(code=code):
                student = Student.objects.create(
                    name=f"Student {code}",
                    dismissal_code=code,
                    grade="3rd",
                    teacher="Test Teacher"
                )
                self.assertEqual(student.dismissal_code, code)

    def test_minimum_length_security(self):
        """FR-3: Test 3-character minimum is enforced"""
        # Test validator function directly
        from dissmissal.utils import validate_dismissal_code_format
        is_valid, message = validate_dismissal_code_format("AB")
        self.assertFalse(is_valid)
        self.assertIn("at least 3 characters", message)
        
        # Test model validation
        with self.assertRaises(ValidationError):
            student = Student(
                name="Test Student",
                dismissal_code="AB",  # Too short
                grade="3rd", 
                teacher="Test Teacher"
            )
            student.full_clean()

    def test_auto_generation_when_blank(self):
        """FR-4: Test auto-generation when field is empty"""
        student = Student.objects.create(
            name="Test Student",
            grade="3rd",
            teacher="Test Teacher"
            # No dismissal_code provided
        )
        
        self.assertIsNotNone(student.dismissal_code)
        self.assertEqual(len(student.dismissal_code), 6)  # Default length
        self.assertTrue(student.dismissal_code.isalnum())

    def test_code_editing_audit_trail(self):
        """FR-5: Test code changes are logged with staff attribution"""
        # Create student
        student = Student.objects.create(
            name="Test Student",
            dismissal_code="ABC123",
            grade="3rd",
            teacher="Test Teacher"
        )
        
        # Mock audit logging
        with patch('dissmissal.utils.log_audit_event') as mock_log:
            # Update code with user context
            student.dismissal_code = "XYZ789"
            student._change_user = self.user
            student._change_ip = "192.168.1.100"
            student.save()
            
            # Verify audit logging was called
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            
            self.assertEqual(call_args[1]['user'], self.user)
            self.assertEqual(call_args[1]['ip_address'], "192.168.1.100")
            self.assertIn("Changed dismissal code", call_args[1]['action'])
            
            details = call_args[1]['details']
            self.assertEqual(details['old_code'], "ABC123")
            self.assertEqual(details['new_code'], "XYZ789")
            self.assertEqual(details['student_name'], "Test Student")

    def test_invalid_code_formats_rejected(self):
        """Test various invalid code formats are rejected"""
        invalid_codes = [
            ("", "cannot be blank"),
            ("AB", "at least 3 characters"),
            ("ABCDEFGHI", "exceed 8 characters"),
            ("ABC@123", "letters and numbers"),
            ("ABC 123", "letters and numbers"),
            ("ABC-123", "letters and numbers")
        ]
        
        for code, expected_error in invalid_codes:
            with self.subTest(code=code):
                with self.assertRaises(ValidationError) as cm:
                    student = Student(
                        name="Test Student",
                        dismissal_code=code,
                        grade="3rd",
                        teacher="Test Teacher"
                    )
                    student.full_clean()
                
                self.assertIn(expected_error, str(cm.exception))

    def test_unique_code_constraint_maintained(self):
        """Test that unique constraint is still enforced"""
        # Create first student
        Student.objects.create(
            name="Student One",
            dismissal_code="ABC123",
            grade="3rd",
            teacher="Teacher One"
        )
        
        # Try to create second student with same code
        with self.assertRaises(ValidationError):
            student2 = Student(
                name="Student Two", 
                dismissal_code="ABC123",  # Duplicate
                grade="4th",
                teacher="Teacher Two"
            )
            student2.full_clean()


class EditableDismissalCodesAdminTests(TestCase):
    """Test admin interface integration"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="admin",
            email="admin@school.edu",
            password="adminpass123",
            is_staff=True,
            is_superuser=True
        )
        self.site = AdminSite()
        self.admin = StudentAdmin(Student, self.site)

    def test_admin_code_editing_interface(self):
        """FR-7: Test admin interface allows code editing"""
        # Check that dismissal_code is not in readonly_fields
        self.assertNotIn('dismissal_code', self.admin.readonly_fields)
        
        # Check that dismissal_code is in search_fields
        self.assertIn('dismissal_code', self.admin.search_fields)

    def test_admin_save_model_audit_logging(self):
        """Test admin interface adds user context for audit logging"""
        request = self.factory.post('/admin/dissmissal/student/')
        request.user = self.user
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        
        # Add session to request
        request.session = {}
        
        student = Student(
            name="Test Student",
            dismissal_code="ABC123",
            grade="3rd",
            teacher="Test Teacher"
        )
        
        # Test save_model method
        self.admin.save_model(request, student, None, False)
        
        # Check that user context was added
        self.assertEqual(student._change_user, self.user)
        self.assertEqual(student._change_ip, '192.168.1.100')

    def test_admin_actions_available(self):
        """Test that admin actions are available"""
        expected_actions = ["reset_to_waiting", "deactivate_students", "generate_new_codes"]
        for action in expected_actions:
            self.assertIn(action, self.admin.actions)


class CSVImportCommandTests(TestCase):
    """Test CSV import functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="admin",
            password="adminpass123", 
            is_staff=True,
            is_superuser=True
        )

    def create_test_csv(self, data):
        """Helper to create temporary CSV file"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        writer = csv.writer(temp_file)
        writer.writerow(['Name', 'Dismissal Code', 'Grade', 'Teacher'])
        for row in data:
            writer.writerow(row)
        temp_file.close()
        return temp_file.name

    def tearDown(self):
        # Clean up temporary files
        for file in getattr(self, '_temp_files', []):
            if os.path.exists(file):
                os.unlink(file)

    def test_bulk_csv_import_validation(self):
        """FR-6: Test CSV import validates before importing"""
        csv_data = [
            ["Student One", "ABC123", "3rd", "Teacher One"],
            ["Student Two", "XYZ789", "4th", "Teacher Two"],
            ["Student Three", "DEF456", "5th", "Teacher Three"]
        ]
        
        csv_file = self.create_test_csv(csv_data)
        self._temp_files = [csv_file]
        
        # Test dry run
        call_command('import_dismissal_codes', csv_file, '--dry-run', verbosity=0)
        
        # No students should be created in dry run
        self.assertEqual(Student.objects.count(), 0)

    def test_csv_import_creates_students(self):
        """Test CSV import actually creates students"""
        csv_data = [
            ["Student One", "ABC123", "3rd", "Teacher One"],
            ["Student Two", "XYZ789", "4th", "Teacher Two"]
        ]
        
        csv_file = self.create_test_csv(csv_data)
        self._temp_files = [csv_file]
        
        # Import for real
        call_command('import_dismissal_codes', csv_file, verbosity=0)
        
        # Check students were created
        self.assertEqual(Student.objects.count(), 2)
        
        student1 = Student.objects.get(name="Student One")
        self.assertEqual(student1.dismissal_code, "ABC123")
        self.assertEqual(student1.grade, "3rd")
        self.assertEqual(student1.teacher, "Teacher One")

    def test_csv_import_update_existing(self):
        """Test CSV import can update existing students"""
        # Create existing student
        existing = Student.objects.create(
            name="Student One",
            dismissal_code="OLD123",
            grade="2nd",
            teacher="Old Teacher"
        )
        
        csv_data = [
            ["Student One", "NEW456", "3rd", "New Teacher"]
        ]
        
        csv_file = self.create_test_csv(csv_data)
        self._temp_files = [csv_file]
        
        # Import with update flag
        call_command('import_dismissal_codes', csv_file, '--update-existing', verbosity=0)
        
        # Check student was updated
        existing.refresh_from_db()
        self.assertEqual(existing.dismissal_code, "NEW456")
        self.assertEqual(existing.grade, "3rd")
        self.assertEqual(existing.teacher, "New Teacher")

    def test_csv_import_validation_errors(self):
        """Test CSV import handles validation errors"""
        csv_data = [
            ["Student One", "AB", "3rd", "Teacher One"],  # Code too short
            ["Student Two", "ABCDEFGHI", "4th", "Teacher Two"],  # Code too long
            ["", "ABC123", "5th", "Teacher Three"]  # Missing name
        ]
        
        csv_file = self.create_test_csv(csv_data)
        self._temp_files = [csv_file]
        
        # Import should handle errors gracefully
        call_command('import_dismissal_codes', csv_file, verbosity=0)
        
        # No students should be created due to validation errors
        self.assertEqual(Student.objects.count(), 0)

    def test_csv_import_duplicate_codes_prevented(self):
        """Test CSV import prevents duplicate dismissal codes"""
        # Create existing student
        Student.objects.create(
            name="Existing Student",
            dismissal_code="ABC123",
            grade="2nd",
            teacher="Existing Teacher"
        )
        
        csv_data = [
            ["New Student", "ABC123", "3rd", "New Teacher"]  # Duplicate code
        ]
        
        csv_file = self.create_test_csv(csv_data)
        self._temp_files = [csv_file]
        
        # Import should fail due to duplicate code
        call_command('import_dismissal_codes', csv_file, verbosity=0)
        
        # Only original student should exist
        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(Student.objects.first().name, "Existing Student")


class SecurityTests(TestCase):
    """Test security requirements"""

    def test_enumeration_prevention(self):
        """SR-1: Test 3-character minimum prevents enumeration attacks"""
        # Single digit codes should be rejected
        from dissmissal.utils import validate_dismissal_code_format
        
        for code in ["1", "2", "A", "B"]:
            with self.subTest(code=code):
                is_valid, message = validate_dismissal_code_format(code)
                self.assertFalse(is_valid)
                self.assertIn("at least 3 characters", message)

    def test_weak_code_warnings(self):
        """SR-2: Test system provides helpful warnings for weak codes"""
        from dissmissal.utils import validate_dismissal_code_format
        
        is_valid, message = validate_dismissal_code_format("AB")
        self.assertFalse(is_valid)
        self.assertIn("Consider codes like '101', '205', or 'ABC'", message)

    def test_audit_trail_completeness(self):
        """SR-4: Test complete audit trail with IP tracking"""
        student = Student.objects.create(
            name="Test Student",
            dismissal_code="ABC123",
            grade="3rd",
            teacher="Test Teacher"
        )
        
        user = User.objects.create_user(
            username="teststaff",
            password="testpass123",
            is_staff=True
        )
        
        with patch('dissmissal.utils.log_audit_event') as mock_log:
            # Update with full audit context
            student.dismissal_code = "XYZ789"
            student._change_user = user
            student._change_ip = "203.0.113.195"
            student.save()
            
            # Verify complete audit trail
            mock_log.assert_called_once()
            call_args = mock_log.call_args[1]
            
            self.assertEqual(call_args['user'], user)
            self.assertEqual(call_args['ip_address'], "203.0.113.195")
            
            details = call_args['details']
            self.assertIn('student_id', details)
            self.assertIn('student_name', details)
            self.assertIn('old_code', details)
            self.assertIn('new_code', details)
            self.assertIn('grade', details)
            self.assertIn('teacher', details)


class BackwardCompatibilityTests(TestCase):
    """Test backward compatibility with existing system"""

    def test_existing_6_char_codes_still_valid(self):
        """Test existing 6-character codes remain valid"""
        student = Student.objects.create(
            name="Test Student",
            dismissal_code="ABC123",  # 6 characters (existing format)
            grade="3rd",
            teacher="Test Teacher"
        )
        
        self.assertEqual(student.dismissal_code, "ABC123")

    def test_auto_generation_still_6_chars(self):
        """Test auto-generated codes are still 6 characters by default"""
        student = Student.objects.create(
            name="Test Student",
            grade="3rd", 
            teacher="Test Teacher"
            # No dismissal_code - should auto-generate
        )
        
        self.assertEqual(len(student.dismissal_code), 6)
        self.assertTrue(student.dismissal_code.isalnum())

    def test_mobile_api_compatibility(self):
        """Test mobile APIs work with both 3-char and 6-char codes"""
        # Create students with different code lengths
        student_3char = Student.objects.create(
            name="Student 3",
            dismissal_code="ABC",
            grade="3rd",
            teacher="Teacher"
        )
        
        student_6char = Student.objects.create(
            name="Student 6", 
            dismissal_code="ABC123",
            grade="4th",
            teacher="Teacher"
        )
        
        # Both should be found by their codes
        self.assertEqual(Student.objects.get(dismissal_code="ABC"), student_3char)
        self.assertEqual(Student.objects.get(dismissal_code="ABC123"), student_6char)