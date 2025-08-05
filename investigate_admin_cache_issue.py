#!/usr/bin/env python
"""
Investigation script for Django admin cache issue
Based on admin-interface-cache-issue-analysis.md findings
"""

import os
import django
from django.conf import settings

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'opendiss.settings')
django.setup()

from dissmissal.models import Student
from django.db import transaction
from django.core.cache import cache
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_direct_model_save():
    """Phase 1.1: Test direct Student model save to check database persistence"""
    print('=== Phase 1.1: Testing Direct Model Save ===')
    
    try:
        student = Student.objects.get(id=29)
        original_status = student.current_status
        print(f'Before save - Status: {original_status}')
        
        # Change status to something different
        new_status = 'PARENT_ARRIVED' if original_status != 'PARENT_ARRIVED' else 'PICKED_UP'
        student.current_status = new_status
        student.save()
        print(f'After save() call - Status: {student.current_status}')
        
        # Refresh from database
        student.refresh_from_db()
        print(f'After refresh_from_db() - Status: {student.current_status}')
        
        # Test with fresh query
        fresh_student = Student.objects.get(id=29)
        print(f'Fresh query - Status: {fresh_student.current_status}')
        
        # Check if save actually persisted
        if fresh_student.current_status == new_status:
            print('✅ Direct model save is working correctly')
            return True
        else:
            print('❌ Direct model save failed to persist')
            return False
        
    except Exception as e:
        print(f'❌ Error in direct model save test: {e}')
        return False

def analyze_student_model():
    """Phase 1.2: Review Student model save method and signals"""
    print('\n=== Phase 1.2: Analyzing Student Model ===')
    
    from dissmissal.models import Student
    import inspect
    
    # Check if Student has custom save method
    if hasattr(Student, 'save'):
        save_method = inspect.getsource(Student.save)
        print('Student model has custom save method:')
        print(save_method)
    else:
        print('Student model uses default Django save method')
    
    # Check for Django signals
    from django.db.models.signals import pre_save, post_save
    
    pre_save_receivers = pre_save._live_receivers(sender=Student)
    post_save_receivers = post_save._live_receivers(sender=Student)
    
    print(f'Pre-save signal receivers: {len(pre_save_receivers)}')
    print(f'Post-save signal receivers: {len(post_save_receivers)}')
    
    if pre_save_receivers:
        print('Pre-save receivers found - may be interfering with saves')
    if post_save_receivers:
        print('Post-save receivers found - may be interfering with saves')

def check_admin_configuration():
    """Phase 1.3: Check Django admin configuration"""
    print('\n=== Phase 1.3: Checking Admin Configuration ===')
    
    try:
        from dissmissal.admin import StudentAdmin
        from django.contrib import admin
        
        # Check if StudentAdmin has custom save_model method
        if hasattr(StudentAdmin, 'save_model'):
            import inspect
            save_model_method = inspect.getsource(StudentAdmin.save_model)
            print('StudentAdmin has custom save_model method:')
            print(save_model_method)
        else:
            print('StudentAdmin uses default save_model method')
            
        # Check admin registration
        if Student in admin.site._registry:
            admin_class = admin.site._registry[Student]
            print(f'Student model registered with admin class: {admin_class.__class__.__name__}')
        else:
            print('❌ Student model not registered with admin')
            
    except Exception as e:
        print(f'❌ Error checking admin configuration: {e}')

def test_cache_configuration():
    """Phase 1.4: Test cache backend configuration"""
    print('\n=== Phase 1.4: Testing Cache Configuration ===')
    
    from django.core.cache import cache
    from django.conf import settings
    
    print(f'Cache backend configuration:')
    for cache_name, cache_config in settings.CACHES.items():
        print(f'  {cache_name}: {cache_config["BACKEND"]}')
    
    # Test cache operations
    test_key = 'admin_cache_test'
    test_value = 'test_value_123'
    
    cache.set(test_key, test_value, 60)
    cached_value = cache.get(test_key)
    
    print(f'Cache test - Set: {test_value}, Get: {cached_value}')
    
    if cached_value == test_value:
        print('✅ Cache backend is working correctly')
        return True
    else:
        print('❌ Cache backend has issues')
        return False

def test_admin_save_simulation():
    """Test simulating admin save operation"""
    print('\n=== Testing Admin Save Simulation ===')
    
    try:
        from dissmissal.admin import StudentAdmin
        from django.contrib.admin.sites import AdminSite
        from django.contrib.auth.models import User
        from django.test import RequestFactory
        
        # Create mock request
        factory = RequestFactory()
        request = factory.post('/admin/dissmissal/student/29/change/')
        request.user = User.objects.get(username='kwhatcher')  # Assuming this user exists
        
        # Get student
        student = Student.objects.get(id=29)
        original_status = student.current_status
        print(f'Original status: {original_status}')
        
        # Simulate admin save
        admin_instance = StudentAdmin(Student, AdminSite())
        student.current_status = 'PARENT_ARRIVED' if original_status != 'PARENT_ARRIVED' else 'PICKED_UP'
        
        print(f'Calling admin save_model with status: {student.current_status}')
        admin_instance.save_model(request, student, None, True)
        
        # Check persistence
        fresh_student = Student.objects.get(id=29)
        print(f'Status after admin save: {fresh_student.current_status}')
        
        if fresh_student.current_status == student.current_status:
            print('✅ Admin save simulation worked')
            return True
        else:
            print('❌ Admin save simulation failed')
            return False
            
    except Exception as e:
        print(f'❌ Error in admin save simulation: {e}')
        return False

def main():
    """Run all investigation phases"""
    print('Starting Django Admin Cache Issue Investigation')
    print('=' * 60)
    
    results = {}
    
    # Phase 1.1: Database transaction analysis
    results['direct_save'] = test_direct_model_save()
    
    # Phase 1.2: Model analysis
    analyze_student_model()
    
    # Phase 1.3: Admin configuration check
    check_admin_configuration()
    
    # Phase 1.4: Cache configuration test
    results['cache_config'] = test_cache_configuration()
    
    # Additional: Admin save simulation
    results['admin_save'] = test_admin_save_simulation()
    
    # Summary
    print(f'\n=== Investigation Results ===')
    print(f'Direct model save: {"PASSED" if results.get("direct_save") else "FAILED"}')
    print(f'Cache configuration: {"PASSED" if results.get("cache_config") else "FAILED"}')
    print(f'Admin save simulation: {"PASSED" if results.get("admin_save") else "FAILED"}')
    
    if all(results.values()):
        print('\n✅ All tests passed - Issue may be browser/session specific')
    else:
        print('\n❌ Some tests failed - Root cause identified')

if __name__ == '__main__':
    main()