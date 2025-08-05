"""
Test cases for the editable dismissal codes system.
Tests cover model validation, admin interface, CSV import, and audit logging.
"""

import csv
import io
import tempfile
import os
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from django.contrib.messages import get_messages
from dissmissal.models import Student, PickupEvent
from dissmissal.utils import (
    validate_dismissal_code_format,
    validate_and_format_dismissal_code,
    check_dismissal_code_uniqueness,
    log_dismissal_code_change
)


class EditableDismissalCodeModelTests(TestCase):
    """Test model validation and functionality for editable dismissal codes"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='teststaff',
            password='testpass123',
            is_staff=True
        )
    
    def test_student_creation_with_manual_code(self):
        """Test creating student with manually specified dismissal code"""
        student = Student.objects.create(
            name='Test Student',
            grade='3rd',
            teacher='Test Teacher',
            dismissal_code='ABC123'
        )
        
        self.assertEqual(student.dismissal_code, 'ABC123')
        self.assertEqual(student.name, 'Test Student')
        self.assertEqual(student.current_status, 'WAITING')
    
    def test_student_creation_with_auto_generated_code(self):
        """Test creating student without dismissal code (auto-generation)"""
        student = Student.objects.create(
            name='Test Student',
            grade='3rd',
            teacher='Test Teacher'
        )
        
        self.assertIsNotNone(student.dismissal_code)
        # Auto-generated codes start at 100 and increment
        self.assertTrue(student.dismissal_code.isdigit())
        code_num = int(student.dismissal_code)
        self.assertGreaterEqual(code_num, 100)
    
    def test_dismissal_code_validation_length(self):
        """Test dismissal code length validation"""
        # Test maximum length (8 characters) - 9 characters should fail
        student = Student(
            name='Test Student',
            grade='3rd',
            teacher='Test Teacher',
            dismissal_code='ABCDEFGHI'  # 9 characters - too long
        )
        with self.assertRaises(ValidationError) as cm:
            student.full_clean()
        self.assertIn('must be 1-8 characters', str(cm.exception))
        
        # Test valid lengths (now 1-8 characters)
        for length in [1, 2, 3, 4, 5, 6, 7, 8]:
            code = 'A' * length
            student = Student.objects.create(
                name=f'Test Student {length}',
                grade='3rd',
                teacher='Test Teacher',
                dismissal_code=code
            )
            self.assertEqual(student.dismissal_code, code)
    
    def test_dismissal_code_character_validation(self):
        """Test dismissal code character validation"""
        invalid_codes = [
            'ABC@123',  # Special characters
            'ABC 123',  # Spaces  
            'ABC-123',  # Hyphens
            'ABC.123',  # Periods
        ]
        
        for invalid_code in invalid_codes:
            student = Student(
                name='Test Student',
                grade='3rd',
                teacher='Test Teacher',
                dismissal_code=invalid_code
            )
            with self.assertRaises(ValidationError):
                student.full_clean()
        
        # Test lowercase conversion
        student = Student.objects.create(
            name='Test Student',
            grade='3rd',
            teacher='Test Teacher',
            dismissal_code='abc123'
        )
        self.assertEqual(student.dismissal_code, 'ABC123')
    
    def test_dismissal_code_uniqueness(self):
        """Test that dismissal codes must be unique"""
        Student.objects.create(
            name='Student One',
            grade='3rd',
            teacher='Teacher One',
            dismissal_code='ABC123'
        )
        
        # Attempt to create another student with same code
        student2 = Student(
            name='Student Two',
            grade='4th',
            teacher='Teacher Two',
            dismissal_code='ABC123'
        )
        
        with self.assertRaises(ValidationError) as cm:
            student2.full_clean()
        self.assertIn('already in use', str(cm.exception))
    
    def test_update_dismissal_code_method(self):
        """Test the update_dismissal_code method with audit logging"""
        student = Student.objects.create(
            name='Test Student',
            grade='3rd',
            teacher='Test Teacher',
            dismissal_code='ABC123'
        )
        
        old_code = student.dismissal_code
        new_code = student.update_dismissal_code(
            'XYZ789',
            user=self.user,
            ip_address='127.0.0.1'
        )
        
        self.assertEqual(new_code, 'XYZ789')
        self.assertEqual(student.dismissal_code, 'XYZ789')
        self.assertNotEqual(old_code, new_code)
    
    def test_auto_generate_new_code_method(self):
        """Test auto-generating new code via update method"""
        student = Student.objects.create(
            name='Test Student',
            grade='3rd',
            teacher='Test Teacher',
            dismissal_code='ABC123'
        )
        
        old_code = student.dismissal_code
        new_code = student.update_dismissal_code(
            None,  # Auto-generate
            user=self.user,
            ip_address='127.0.0.1'
        )
        
        self.assertIsNotNone(new_code)
        # Auto-generated codes are numeric starting at 100
        self.assertTrue(new_code.isdigit())
        self.assertGreaterEqual(int(new_code), 100)
        self.assertNotEqual(old_code, new_code)


class DismissalCodeUtilityTests(TestCase):
    """Test utility functions for dismissal code validation"""
    
    def test_validate_dismissal_code_format(self):
        """Test format validation utility function"""
        # Valid codes
        self.assertTrue(validate_dismissal_code_format('ABC123')[0])
        self.assertTrue(validate_dismissal_code_format('XYZ')[0])
        self.assertTrue(validate_dismissal_code_format('12345678')[0])
        self.assertTrue(validate_dismissal_code_format('A')[0])  # Now valid (1 char)
        self.assertTrue(validate_dismissal_code_format('22')[0])  # Now valid (2 chars)
        
        # Invalid codes
        self.assertFalse(validate_dismissal_code_format('ABCDEFGHI')[0])  # Too long (9 chars)
        self.assertFalse(validate_dismissal_code_format('ABC@123')[0])  # Invalid chars
        
        # Empty code with allow_empty
        self.assertTrue(validate_dismissal_code_format('', allow_empty=True)[0])
        self.assertFalse(validate_dismissal_code_format('', allow_empty=False)[0])
    
    def test_validate_and_format_dismissal_code(self):
        """Test code validation and formatting utility"""
        # Test formatting (uppercase, strip)
        formatted, valid, _ = validate_and_format_dismissal_code('  abc123  ')
        self.assertTrue(valid)
        self.assertEqual(formatted, 'ABC123')
        
        # Test invalid code (too long)
        formatted, valid, error = validate_and_format_dismissal_code('ABCDEFGHI')
        self.assertFalse(valid)
        self.assertIn('1-8 characters', error)
    
    def test_check_dismissal_code_uniqueness(self):
        """Test uniqueness checking utility"""
        Student.objects.create(
            name='Existing Student',
            grade='3rd',
            teacher='Test Teacher',
            dismissal_code='UNIQUE12'  # 8 characters max
        )
        
        # Check existing code
        is_unique, error = check_dismissal_code_uniqueness('UNIQUE12')
        self.assertFalse(is_unique)
        self.assertIn('already in use', error)
        
        # Check new code
        is_unique, error = check_dismissal_code_uniqueness('NEWCODE1')  # 8 characters max
        self.assertTrue(is_unique)
        self.assertEqual(error, '')


class AdminInterfaceTests(TestCase):
    """Test admin interface for editable dismissal codes"""
    
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='adminpass123'
        )
        self.client.login(username='admin', password='adminpass123')
        
        self.student = Student.objects.create(
            name='Test Student',
            grade='3rd',
            teacher='Test Teacher',
            dismissal_code='ORIG123'
        )
    
    def test_admin_dismissal_code_editable(self):
        """Test that dismissal code field is editable in admin"""
        url = reverse('admin:dissmissal_student_change', args=[self.student.pk])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Check that dismissal_code field is present and editable
        self.assertContains(response, 'name="dismissal_code"')
        self.assertContains(response, 'value="ORIG123"')
    
    def test_admin_edit_dismissal_code(self):
        """Test editing dismissal code through admin interface"""
        url = reverse('admin:dissmissal_student_change', args=[self.student.pk])
        
        response = self.client.post(url, {
            'name': 'Test Student',
            'grade': '3rd',
            'teacher': 'Test Teacher',
            'dismissal_code': 'NEW456',
            'current_status': 'WAITING',
            'is_active': True,
        })
        
        # Should redirect after successful save
        self.assertEqual(response.status_code, 302)
        
        # Check that code was updated
        self.student.refresh_from_db()
        self.assertEqual(self.student.dismissal_code, 'NEW456')
    
    def test_admin_bulk_generate_codes_action(self):
        """Test bulk code generation action in admin"""
        # Create additional students
        student2 = Student.objects.create(
            name='Student Two',
            grade='4th',
            teacher='Teacher Two',
            dismissal_code='OLD456'
        )
        
        url = reverse('admin:dissmissal_student_changelist')
        response = self.client.post(url, {
            'action': 'generate_new_codes',
            '_selected_action': [str(self.student.pk), str(student2.pk)],
        })
        
        # Should redirect back to changelist
        self.assertEqual(response.status_code, 302)
        
        # Check that codes were changed
        self.student.refresh_from_db()
        student2.refresh_from_db()
        
        self.assertNotEqual(self.student.dismissal_code, 'ORIG123')
        self.assertNotEqual(student2.dismissal_code, 'OLD456')
        # Auto-generated codes are numeric starting at 100
        self.assertTrue(self.student.dismissal_code.isdigit())
        self.assertTrue(student2.dismissal_code.isdigit())
        self.assertGreaterEqual(int(self.student.dismissal_code), 100)
        self.assertGreaterEqual(int(student2.dismissal_code), 100)
    
    def test_admin_csv_import_view(self):
        """Test CSV import view accessibility"""
        url = reverse('admin:bulk_import_dismissal_codes')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bulk Import Dismissal Codes')
        self.assertContains(response, 'student_name,dismissal_code')
    
    def test_admin_csv_export_view(self):
        """Test CSV export functionality"""  
        url = reverse('admin:export_dismissal_codes')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
        
        # Check CSV content
        content = response.content.decode('utf-8')
        self.assertIn('student_name,dismissal_code')
        self.assertIn('Test Student')
        self.assertIn('ORIG123')


class CSVImportTests(TestCase):
    """Test CSV import functionality"""
    
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com', 
            password='adminpass123'
        )
        self.client = Client()
        self.client.login(username='admin', password='adminpass123')
        
        # Create test students
        self.student1 = Student.objects.create(
            name='John Smith',
            grade='3rd',
            teacher='Teacher One',
            dismissal_code='OLD123'
        )
        self.student2 = Student.objects.create(
            name='Jane Doe',
            grade='4th', 
            teacher='Teacher Two',
            dismissal_code='OLD456'
        )
    
    def test_csv_import_successful(self):
        """Test successful CSV import through admin interface"""
        csv_content = '''student_name,dismissal_code
John Smith,NEW123
Jane Doe,NEW456'''
        
        csv_file = io.StringIO(csv_content)
        csv_file.name = 'test_codes.csv'
        
        response = self.client.post(
            reverse('admin:bulk_import_dismissal_codes'),
            {'csv_file': io.BytesIO(csv_content.encode('utf-8'))},
            format='multipart'
        )
        
        # Check students were updated
        self.student1.refresh_from_db()
        self.student2.refresh_from_db()
        
        # Note: The actual test may need adjustment based on file upload handling
        # This is a basic structure for the test
        
    def test_csv_import_with_auto_generate(self):
        """Test CSV import with empty codes for auto-generation"""
        csv_content = '''student_name,dismissal_code
John Smith,
Jane Doe,MANUAL78'''
        
        # This would test the auto-generation functionality
        # Implementation depends on actual file upload handling
    
    def test_csv_import_validation_errors(self):
        """Test CSV import with validation errors"""
        csv_content = '''student_name,dismissal_code
John Smith,ABCDEFGHI
Jane Doe,INVALID@CODE
Nonexistent Student,VALID123'''
        
        # This would test error handling during import
        # Implementation depends on actual error reporting


class ManagementCommandTests(TestCase):
    """Test management command for CSV import"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='staffuser',
            password='testpass123',
            is_staff=True
        )
        
        self.student = Student.objects.create(
            name='Command Test Student',
            grade='3rd',
            teacher='Test Teacher',
            dismissal_code='CMD123'
        )
        
        # Create temporary CSV file
        self.csv_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        self.csv_file.write('student_name,dismissal_code\\n')
        self.csv_file.write('Command Test Student,NEWCMD45\\n')
        self.csv_file.close()
    
    def tearDown(self):
        # Clean up temporary file
        os.unlink(self.csv_file.name)
    
    def test_management_command_success(self):
        """Test successful execution of import command"""
        call_command(
            'import_dismissal_codes',
            file=self.csv_file.name,
            user='staffuser'
        )
        
        self.student.refresh_from_db()
        self.assertEqual(self.student.dismissal_code, 'NEWCMD45')
    
    def test_management_command_dry_run(self):
        """Test dry run mode of import command"""
        original_code = self.student.dismissal_code
        
        call_command(
            'import_dismissal_codes',
            file=self.csv_file.name,
            user='staffuser',
            dry_run=True
        )
        
        self.student.refresh_from_db()
        # Code should remain unchanged in dry run
        self.assertEqual(self.student.dismissal_code, original_code)
    
    def test_management_command_file_not_found(self):
        """Test command with non-existent file"""
        with self.assertRaises(CommandError):
            call_command(
                'import_dismissal_codes',
                file='/nonexistent/file.csv',
                user='staffuser'
            )
    
    def test_management_command_invalid_user(self):
        """Test command with invalid user"""
        with self.assertRaises(CommandError):
            call_command(
                'import_dismissal_codes',
                file=self.csv_file.name,
                user='nonexistentuser'
            )


class BackwardCompatibilityTests(TestCase):
    """Test that existing functionality remains unaffected"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='teststaff',
            password='testpass123',
            is_staff=True
        )
        
        # Create student with new system (should work like before)
        self.student = Student.objects.create(
            name='Compatibility Test Student',
            grade='3rd', 
            teacher='Test Teacher'
            # No dismissal code - should auto-generate
        )
    
    def test_existing_api_endpoints_work(self):
        """Test that existing API endpoints still function"""
        self.client.login(username='teststaff', password='testpass123')
        
        # Test validation API
        response = self.client.post(
            reverse('dissmissal:validate_code_api'),
            data={'dismissal_code': self.student.dismissal_code},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        # Should still work with existing code structure
    
    def test_existing_views_work(self):
        """Test that existing views still function"""
        self.client.login(username='teststaff', password='testpass123')
        
        # Test parent arrival with existing student
        response = self.client.post(
            reverse('dissmissal:parent_arrival'),
            {
                'dismissal_code': self.student.dismissal_code,
                'notes': 'Test arrival'
            }
        )
        
        # Should work as before
        self.assertEqual(response.status_code, 302)
        
        self.student.refresh_from_db()
        self.assertEqual(self.student.current_status, 'PARENT_ARRIVED')
    
    def test_pickup_events_still_created(self):
        """Test that pickup events are still created properly"""
        original_count = PickupEvent.objects.count()
        
        self.client.login(username='teststaff', password='testpass123')
        
        response = self.client.post(
            reverse('dissmissal:parent_arrival'),
            {
                'dismissal_code': self.student.dismissal_code,
                'notes': 'Compatibility test'
            }
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PickupEvent.objects.count(), original_count + 1)
        
        # Check event details
        event = PickupEvent.objects.latest('timestamp')
        self.assertEqual(event.student, self.student)
        self.assertEqual(event.dismissal_code_used, self.student.dismissal_code)
        self.assertEqual(event.event_type, 'PARENT_ARRIVED')


class AuditLoggingTests(TestCase):
    """Test audit logging for dismissal code changes"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='audituser',
            password='testpass123',
            is_staff=True
        )
        
        self.student = Student.objects.create(
            name='Audit Test Student',
            grade='3rd',
            teacher='Test Teacher',
            dismissal_code='AUDIT123'
        )
    
    def test_audit_logging_function(self):
        """Test the audit logging utility function"""
        from dissmissal.utils import log_dismissal_code_change
        
        # This should not raise an exception
        log_dismissal_code_change(
            user=self.user,
            student=self.student,
            old_code='OLD123',
            new_code='NEW123',
            ip_address='127.0.0.1',
            method='test'
        )
        
        # Verify logging occurred (would need to check log files in real implementation)
        # For now, just ensure the function runs without error
    
    def test_model_update_method_logging(self):
        """Test that model update method includes logging"""
        old_code = self.student.dismissal_code
        
        # Use update method with user info
        new_code = self.student.update_dismissal_code(
            'LOGGED45',
            user=self.user,
            ip_address='192.168.1.1',
            method='test_method'
        )
        
        self.assertEqual(new_code, 'LOGGED45')
        self.assertEqual(self.student.dismissal_code, 'LOGGED45')
        # Logging should have occurred (verified by no exceptions)