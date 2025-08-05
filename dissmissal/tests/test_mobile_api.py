"""
Tests for Mobile API Endpoints

Tests the mobile interface API endpoints for greeter and releaser functionality.
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.cache import cache
from dissmissal.models import Student, PickupEvent
import json


class MobileAPITests(TestCase):
    """Test cases for mobile interface API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        cache.clear()
        
        # Create test user
        self.user = User.objects.create_user(
            username='teststaff',
            password='testpass123',
            first_name='Test',
            last_name='Staff'
        )
        
        # Create test students
        self.student1 = Student.objects.create(
            name='Alice Johnson',
            dismissal_code='ABC123',
            grade='3',
            teacher='Ms. Smith',
            current_status='WAITING'
        )
        
        self.student2 = Student.objects.create(
            name='Bob Wilson',
            dismissal_code='XYZ789',
            grade='4',
            teacher='Mr. Jones',
            current_status='PARENT_ARRIVED'
        )
        
        self.student3 = Student.objects.create(
            name='Carol Brown',
            dismissal_code='DEF456',
            grade='5',
            teacher='Mrs. Davis',
            current_status='PICKED_UP'
        )
        
        self.client = Client()
        self.client.login(username='teststaff', password='testpass123')
    
    def test_greeter_submit_success(self):
        """Test successful parent arrival submission"""
        response = self.client.post('/dissmissal/api/greeter-submit/', {
            'code': 'ABC123'
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('Alice Johnson', data['message'])
        self.assertIn('Grade 3', data['message'])
        self.assertIn('Ms. Smith', data['message'])
        
        # Check that student status was updated
        self.student1.refresh_from_db()
        self.assertEqual(self.student1.current_status, 'PARENT_ARRIVED')
        
        # Check that pickup event was created
        event = PickupEvent.objects.filter(
            student=self.student1,
            event_type='PARENT_ARRIVED'
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.staff_member, self.user)
    
    def test_greeter_submit_duplicate(self):
        """Test submitting code for student whose parent already arrived"""
        response = self.client.post('/dissmissal/api/greeter-submit/', {
            'code': 'XYZ789'  # student2 already has PARENT_ARRIVED status
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data.get('duplicate'))
        self.assertIn('Bob Wilson', data['message'])
        self.assertIn('already here', data['message'])
    
    def test_greeter_submit_already_picked_up(self):
        """Test submitting code for student already picked up"""
        response = self.client.post('/dissmissal/api/greeter-submit/', {
            'code': 'DEF456'  # student3 has PICKED_UP status
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Carol Brown', data['message'])
        self.assertIn('already picked up', data['message'])
    
    def test_greeter_submit_invalid_code(self):
        """Test submitting invalid dismissal code"""
        response = self.client.post('/dissmissal/api/greeter-submit/', {
            'code': 'INVALID'
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Invalid student code', data['message'])
    
    def test_greeter_submit_empty_code(self):
        """Test submitting empty code"""
        response = self.client.post('/dissmissal/api/greeter-submit/', {
            'code': ''
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Please enter a student code', data['message'])
    
    def test_greeter_submit_invalid_format(self):
        """Test submitting code with invalid format"""
        response = self.client.post('/dissmissal/api/greeter-submit/', {
            'code': 'AB!'  # Contains special character
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Invalid code format', data['message'])
    
    def test_greeter_submit_unauthenticated(self):
        """Test that unauthenticated requests are rejected"""
        self.client.logout()
        response = self.client.post('/dissmissal/api/greeter-submit/', {
            'code': 'ABC123'
        })
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
    
    def test_releaser_data_success(self):
        """Test getting releaser data successfully"""
        response = self.client.get('/dissmissal/api/releaser-data/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('students', data)
        
        students = data['students']
        self.assertEqual(len(students), 1)  # Only student2 has PARENT_ARRIVED status
        
        student_data = students[0]
        self.assertEqual(student_data['name'], 'Bob Wilson')
        self.assertEqual(student_data['code'], 'XYZ789')
        self.assertEqual(student_data['grade'], '4')
        self.assertEqual(student_data['teacher'], 'Mr. Jones')
        self.assertIn('arrived_at', student_data)
    
    def test_releaser_data_empty(self):
        """Test releaser data when no students are pending"""
        # Set all students to non-pending status
        Student.objects.filter(current_status='PARENT_ARRIVED').update(
            current_status='PICKED_UP'
        )
        
        response = self.client.get('/dissmissal/api/releaser-data/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['students']), 0)
    
    def test_releaser_data_unauthenticated(self):
        """Test that unauthenticated requests are rejected"""
        self.client.logout()
        response = self.client.get('/dissmissal/api/releaser-data/')
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
    
    def test_complete_pickup_success(self):
        """Test successful pickup completion"""
        response = self.client.post('/dissmissal/api/complete-pickup/', {
            'student_id': self.student2.id  # student2 has PARENT_ARRIVED status
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('Bob Wilson', data['message'])
        self.assertIn('pickup complete', data['message'])
        
        # Check that student status was updated
        self.student2.refresh_from_db()
        self.assertEqual(self.student2.current_status, 'PICKED_UP')
        
        # Check that pickup event was created
        event = PickupEvent.objects.filter(
            student=self.student2,
            event_type='STUDENT_PICKED_UP'
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.staff_member, self.user)
    
    def test_complete_pickup_not_ready(self):
        """Test pickup completion for student not ready"""
        response = self.client.post('/dissmissal/api/complete-pickup/', {
            'student_id': self.student1.id  # student1 has WAITING status
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('not ready for pickup', data['message'])
        
        # Check that student status was not changed
        self.student1.refresh_from_db()
        self.assertEqual(self.student1.current_status, 'WAITING')
    
    def test_complete_pickup_invalid_id(self):
        """Test pickup completion with invalid student ID"""
        response = self.client.post('/dissmissal/api/complete-pickup/', {
            'student_id': 'invalid'
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Invalid student ID', data['message'])
    
    def test_complete_pickup_missing_id(self):
        """Test pickup completion with missing student ID"""
        response = self.client.post('/dissmissal/api/complete-pickup/', {})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Student ID required', data['message'])
    
    def test_complete_pickup_nonexistent_id(self):
        """Test pickup completion with nonexistent student ID"""
        response = self.client.post('/dissmissal/api/complete-pickup/', {
            'student_id': 99999
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('not found', data['message'])
    
    def test_complete_pickup_unauthenticated(self):
        """Test that unauthenticated requests are rejected"""
        self.client.logout()
        response = self.client.post('/dissmissal/api/complete-pickup/', {
            'student_id': self.student2.id
        })
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)