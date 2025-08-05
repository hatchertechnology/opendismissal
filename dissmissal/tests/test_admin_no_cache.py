"""
Test cases for admin no-cache headers.
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from dissmissal.models import Student


class AdminNoCacheTests(TestCase):
    """Test admin pages have proper no-cache headers"""
    
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
            dismissal_code='TEST123'
        )
    
    def test_admin_changelist_no_cache_headers(self):
        """Test that admin changelist has no-cache headers"""
        url = reverse('admin:dissmissal_student_changelist')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check for no-cache headers
        cache_control = response.get('Cache-Control', '')
        self.assertIn('no-cache', cache_control)
        self.assertIn('no-store', cache_control)
        self.assertIn('must-revalidate', cache_control)
        self.assertIn('max-age=0', cache_control)
        
        self.assertEqual(response.get('Pragma'), 'no-cache')
        self.assertEqual(response.get('Expires'), '0')
    
    def test_admin_change_view_no_cache_headers(self):
        """Test that admin change view has no-cache headers"""
        url = reverse('admin:dissmissal_student_change', args=[self.student.pk])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check for no-cache headers
        cache_control = response.get('Cache-Control', '')
        self.assertIn('no-cache', cache_control)
        self.assertIn('no-store', cache_control)
        self.assertIn('must-revalidate', cache_control)
        
        self.assertEqual(response.get('Pragma'), 'no-cache')
        self.assertEqual(response.get('Expires'), '0')
    
    def test_admin_add_view_no_cache_headers(self):
        """Test that admin add view has no-cache headers"""
        url = reverse('admin:dissmissal_student_add')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check for no-cache headers
        cache_control = response.get('Cache-Control', '')
        self.assertIn('no-cache', cache_control)
        self.assertIn('no-store', cache_control)
        
        self.assertEqual(response.get('Pragma'), 'no-cache')
        self.assertEqual(response.get('Expires'), '0')
    
    def test_admin_shows_fresh_data(self):
        """Test that admin list shows fresh data immediately"""
        # Get initial response
        url = reverse('admin:dissmissal_student_changelist')
        response1 = self.client.get(url)
        self.assertContains(response1, 'Test Student')
        
        # Add new student
        new_student = Student.objects.create(
            name='Fresh Student',
            grade='4th', 
            teacher='Fresh Teacher',
            dismissal_code='FRESH123'
        )
        
        # Get response again - should show new student immediately
        response2 = self.client.get(url)
        self.assertContains(response2, 'Test Student')
        self.assertContains(response2, 'Fresh Student')
        
        # Clean up
        new_student.delete()
    
    def test_queryset_is_fresh(self):
        """Test that get_queryset returns fresh data"""
        from dissmissal.admin import StudentAdmin
        from django.http import HttpRequest
        
        admin = StudentAdmin(Student, None)
        request = HttpRequest()
        
        # Get initial queryset
        queryset1 = admin.get_queryset(request)
        initial_count = queryset1.count()
        
        # Add new student
        new_student = Student.objects.create(
            name='Queryset Test',
            grade='5th',
            teacher='Queryset Teacher', 
            dismissal_code='QS123'
        )
        
        # Get queryset again - should include new student
        queryset2 = admin.get_queryset(request)
        new_count = queryset2.count()
        
        self.assertEqual(new_count, initial_count + 1)
        
        # Verify new student is in queryset
        student_names = [s.name for s in queryset2]
        self.assertIn('Queryset Test', student_names)
        
        # Clean up
        new_student.delete()