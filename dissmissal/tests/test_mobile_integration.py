"""
Mobile Interface Integration Tests

Tests the complete mobile interface workflow from UI to API.
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from dissmissal.models import Student, PickupEvent


class MobileIntegrationTests(TestCase):
    """Integration tests for mobile interfaces"""
    
    def setUp(self):
        """Set up test data"""
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
        
        self.client = Client()
    
    def test_greeter_page_loads(self):
        """Test that greeter page loads correctly"""
        self.client.login(username='teststaff', password='testpass123')
        
        response = self.client.get('/dissmissal/greeter/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Parent Check-in')
        self.assertContains(response, 'Test Staff')
        self.assertContains(response, 'Enter Code')
        self.assertContains(response, '/dissmissal/api/greeter-submit/')
    
    def test_releaser_page_loads(self):
        """Test that releaser page loads correctly"""
        self.client.login(username='teststaff', password='testpass123')
        
        response = self.client.get('/dissmissal/releaser/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Student Release')
        self.assertContains(response, 'Test Staff')
        self.assertContains(response, 'Pending')
        self.assertContains(response, '/dissmissal/api/releaser-data/')
        self.assertContains(response, '/dissmissal/api/complete-pickup/')
    
    def test_greeter_requires_login(self):
        """Test that greeter page requires authentication"""
        response = self.client.get('/dissmissal/greeter/')
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
    
    def test_releaser_requires_login(self):
        """Test that releaser page requires authentication"""
        response = self.client.get('/dissmissal/releaser/')
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
    
    def test_complete_workflow(self):
        """Test complete workflow: greeter -> releaser -> completion"""
        self.client.login(username='teststaff', password='testpass123')
        
        # Step 1: Check greeter shows no students initially ready
        releaser_response = self.client.get('/dissmissal/api/releaser-data/')
        releaser_data = releaser_response.json()
        initial_count = len(releaser_data['students'])
        
        # Step 2: Use greeter to check in a parent
        greeter_response = self.client.post('/dissmissal/api/greeter-submit/', {
            'code': 'ABC123'  # Alice Johnson
        })
        greeter_data = greeter_response.json()
        
        self.assertTrue(greeter_data['success'])
        self.assertIn('Alice Johnson', greeter_data['message'])
        
        # Verify student status changed
        self.student1.refresh_from_db()
        self.assertEqual(self.student1.current_status, 'PARENT_ARRIVED')
        
        # Verify pickup event was created
        event = PickupEvent.objects.filter(
            student=self.student1,
            event_type='PARENT_ARRIVED'
        ).first()
        self.assertIsNotNone(event)
        
        # Step 3: Check releaser now shows the student
        releaser_response = self.client.get('/dissmissal/api/releaser-data/')
        releaser_data = releaser_response.json()
        
        self.assertEqual(len(releaser_data['students']), initial_count + 1)
        
        # Find Alice in the list
        alice_data = None
        for student in releaser_data['students']:
            if student['name'] == 'Alice Johnson':
                alice_data = student
                break
        
        self.assertIsNotNone(alice_data)
        self.assertEqual(alice_data['code'], 'ABC123')
        self.assertEqual(alice_data['grade'], '3')
        self.assertEqual(alice_data['teacher'], 'Ms. Smith')
        
        # Step 4: Complete pickup via releaser
        pickup_response = self.client.post('/dissmissal/api/complete-pickup/', {
            'student_id': self.student1.id
        })
        pickup_data = pickup_response.json()
        
        self.assertTrue(pickup_data['success'])
        self.assertIn('Alice Johnson', pickup_data['message'])
        self.assertIn('pickup complete', pickup_data['message'])
        
        # Verify student status changed
        self.student1.refresh_from_db()
        self.assertEqual(self.student1.current_status, 'PICKED_UP')
        
        # Verify pickup completion event was created
        completion_event = PickupEvent.objects.filter(
            student=self.student1,
            event_type='STUDENT_PICKED_UP'
        ).first()
        self.assertIsNotNone(completion_event)
        
        # Step 5: Check releaser no longer shows the student
        final_releaser_response = self.client.get('/dissmissal/api/releaser-data/')
        final_releaser_data = final_releaser_response.json()
        
        self.assertEqual(len(final_releaser_data['students']), initial_count)
        
        # Verify Alice is no longer in the list
        for student in final_releaser_data['students']:
            self.assertNotEqual(student['name'], 'Alice Johnson')
    
    def test_mobile_templates_are_self_contained(self):
        """Test that mobile templates don't reference external resources"""
        self.client.login(username='teststaff', password='testpass123')
        
        # Test greeter template
        greeter_response = self.client.get('/dissmissal/greeter/')
        greeter_content = greeter_response.content.decode()
        
        # Should not reference external CSS/JS files
        self.assertNotIn('<link', greeter_content.lower())
        self.assertNotIn('<script src=', greeter_content.lower())
        # Should have inline styles and scripts
        self.assertIn('<style>', greeter_content)
        self.assertIn('<script>', greeter_content)
        
        # Test releaser template  
        releaser_response = self.client.get('/dissmissal/releaser/')
        releaser_content = releaser_response.content.decode()
        
        # Should not reference external CSS/JS files
        self.assertNotIn('<link', releaser_content.lower())
        self.assertNotIn('<script src=', releaser_content.lower())
        # Should have inline styles and scripts
        self.assertIn('<style>', releaser_content)
        self.assertIn('<script>', releaser_content)
    
    def test_mobile_templates_have_large_touch_targets(self):
        """Test that mobile templates have appropriately sized touch targets"""
        self.client.login(username='teststaff', password='testpass123')
        
        # Test greeter template
        greeter_response = self.client.get('/dissmissal/greeter/')
        greeter_content = greeter_response.content.decode()
        
        # Should have large touch targets (check for height values >= 60px for mobile accessibility)
        import re
        
        # Check for input and button height declarations
        height_pattern = r'height:\s*(\d+)px'
        heights = re.findall(height_pattern, greeter_content)
        
        # Convert to integers and check we have touch targets >= 60px (mobile accessibility minimum)
        large_heights = [int(h) for h in heights if int(h) >= 60]
        self.assertGreater(len(large_heights), 0, "Greeter should have elements with height >= 60px for touch accessibility")
        
        # Test releaser template
        releaser_response = self.client.get('/dissmissal/releaser/')
        releaser_content = releaser_response.content.decode()
        
        # Check for button height declarations in releaser
        releaser_heights = re.findall(height_pattern, releaser_content)
        releaser_large_heights = [int(h) for h in releaser_heights if int(h) >= 60]
        self.assertGreater(len(releaser_large_heights), 0, "Releaser should have elements with height >= 60px for touch accessibility")