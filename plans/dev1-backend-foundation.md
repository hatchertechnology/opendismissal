# Developer 1: Backend Foundation & Database

**Developer:** Backend Foundation Lead  
**Branch:** `feature/backend-foundation`  
**Timeline:** Days 1-6 of development  
**Dependencies:** None (foundational work)  

## Project Context

You're building the backend foundation for OpenDismissal, a Django-based school dismissal management system. This system replaces paper-based student pickup processes with a secure, real-time digital solution for staff coordination during dismissal periods.

**Your role:** Create the secure, production-ready foundation that other developers will build upon. Your work enables the core business logic and user interface components.

## Technical Specifications

### Core Architecture Requirements

**Technology Stack:**
- **Framework:** Django 5.2+
- **Database:** PostgreSQL (with SQLite for development)
- **Caching:** Redis for session storage and performance
- **Authentication:** Django's built-in auth system
- **Configuration:** python-decouple with .env files

**Security Requirements:**
- Individual staff authentication (no shared accounts)
- FERPA-compliant audit logging capabilities
- Environment-based configuration (no hardcoded secrets)
- Database-level constraints for data integrity

## Database Schema Implementation

### Core Models

Create these models in `dissmissal/models.py`:

```python
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
import secrets
import string

class Student(models.Model):
    """
    Simplified student model with embedded dismissal code for MVP speed.
    Includes status tracking optimization for dashboard performance.
    """
    name = models.CharField(max_length=100, help_text="Full student name")
    dismissal_code = models.CharField(
        max_length=8, 
        unique=True, 
        db_index=True,
        help_text="Unique 6-8 character code for parent verification"
    )
    grade = models.CharField(max_length=20, help_text="Student grade level")
    teacher = models.CharField(max_length=100, help_text="Homeroom teacher name")
    is_active = models.BooleanField(default=True, help_text="Active in current dismissal")
    
    # Status tracking optimization (from Jake v2.0 plan)
    current_status = models.CharField(
        max_length=20,
        choices=[
            ('WAITING', 'Waiting for Parent'),
            ('PARENT_ARRIVED', 'Parent Has Arrived'),
            ('PICKED_UP', 'Student Picked Up'),
        ],
        default='WAITING',
        db_index=True,
        help_text="Current dismissal status for quick dashboard queries"
    )
    status_updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['dismissal_code']),
            models.Index(fields=['is_active', 'current_status']),
            models.Index(fields=['grade', 'teacher']),
            models.Index(fields=['-created_at']),  # For admin ordering
        ]
        ordering = ['name']
        verbose_name = "Student"
        verbose_name_plural = "Students"
    
    def __str__(self):
        return f"{self.name} ({self.dismissal_code})"
    
    def save(self, *args, **kwargs):
        """Auto-generate dismissal code if not provided"""
        if not self.dismissal_code:
            self.dismissal_code = self.generate_dismissal_code()
        super().save(*args, **kwargs)
    
    @classmethod
    def generate_dismissal_code(cls):
        """Generate cryptographically secure unique dismissal code"""
        while True:
            # Use secrets module for cryptographic security
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) 
                          for _ in range(6))
            if not cls.objects.filter(dismissal_code=code).exists():
                return code
    
    def get_latest_event(self):
        """Get most recent pickup event for this student"""
        return self.pickup_events.order_by('-timestamp').first()
    
    def get_today_events(self):
        """Get all pickup events for today"""
        from django.utils import timezone
        today = timezone.now().date()
        return self.pickup_events.filter(timestamp__date=today).order_by('-timestamp')


class PickupEvent(models.Model):
    """
    Event-driven audit trail for all dismissal actions.
    Provides immutable history for FERPA compliance.
    """
    EVENT_TYPE_CHOICES = [
        ('PARENT_ARRIVED', 'Parent Arrived'),
        ('STUDENT_PICKED_UP', 'Student Picked Up'),
        ('CANCELLED', 'Pickup Cancelled'),
    ]
    
    student = models.ForeignKey(
        Student, 
        on_delete=models.CASCADE,
        related_name='pickup_events',
        help_text="Student this event relates to"
    )
    staff_member = models.ForeignKey(
        User, 
        on_delete=models.PROTECT,  # Protect from accidental staff deletion
        help_text="Staff member who performed this action"
    )
    event_type = models.CharField(
        max_length=20, 
        choices=EVENT_TYPE_CHOICES,
        help_text="Type of dismissal event"
    )
    dismissal_code_used = models.CharField(
        max_length=8,
        help_text="The dismissal code that was used for verification"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="When this event occurred"
    )
    notes = models.TextField(
        blank=True,
        help_text="Optional notes about this event"
    )
    
    # Basic audit fields for FERPA compliance
    ip_address = models.GenericIPAddressField(
        help_text="IP address of the staff member when event occurred"
    )
    
    class Meta:
        indexes = [
            models.Index(fields=['student', '-timestamp']),
            models.Index(fields=['event_type', '-timestamp']),
            models.Index(fields=['staff_member', '-timestamp']),
            models.Index(fields=['-timestamp']),  # For general event queries
        ]
        ordering = ['-timestamp']
        verbose_name = "Pickup Event"
        verbose_name_plural = "Pickup Events"
    
    def __str__(self):
        return f"{self.student.name} - {self.get_event_type_display()} by {self.staff_member.get_full_name() or self.staff_member.username}"
    
    def save(self, *args, **kwargs):
        """Update student status when pickup events are created"""
        super().save(*args, **kwargs)
        
        # Update student's current status based on this event
        if self.event_type == 'PARENT_ARRIVED':
            self.student.current_status = 'PARENT_ARRIVED'
        elif self.event_type == 'STUDENT_PICKED_UP':
            self.student.current_status = 'PICKED_UP'
        elif self.event_type == 'CANCELLED':
            self.student.current_status = 'WAITING'
        
        self.student.save(update_fields=['current_status', 'status_updated_at'])
```

### Performance Manager Classes

Add these custom managers for optimized queries:

```python
class StudentManager(models.Manager):
    """Custom manager for optimized student queries"""
    
    def active_with_events(self):
        """Active students with prefetched latest events"""
        return self.select_related().filter(
            is_active=True
        ).prefetch_related(
            models.Prefetch(
                'pickup_events',
                queryset=PickupEvent.objects.select_related('staff_member')
                                           .order_by('-timestamp')[:3]
            )
        )
    
    def waiting_for_pickup(self):
        """Students waiting for parent or ready for pickup"""
        return self.active_with_events().filter(
            current_status__in=['WAITING', 'PARENT_ARRIVED']
        )
    
    def by_grade(self, grade):
        """Filter students by grade level"""
        return self.active_with_events().filter(grade=grade)

# Add to Student model:
# objects = StudentManager()
```

## Django Project Configuration

### Settings Configuration

Create these settings in `opendiss/settings.py`:

```python
# Add to INSTALLED_APPS
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'django_ratelimit',  # For rate limiting
    
    # Local apps
    'dissmissal',
]

# Database configuration with environment variables
import dj_database_url
from decouple import config

DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL', default='sqlite:///db.sqlite3')
    )
}

# Cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://127.0.0.1:6379/1'),
        'KEY_PREFIX': 'opendismissal',
        'TIMEOUT': 300,  # 5 minutes default
    }
}

# Security settings
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost').split(',')

# Authentication settings
LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/dissmissal/'
LOGOUT_REDIRECT_URL = '/admin/login/'

# Time zone and internationalization
TIME_ZONE = 'America/New_York'  # Adjust for school timezone
USE_TZ = True

# Static files configuration
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Security middleware for production
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Logging configuration for audit trail
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'dissmissal_audit.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'dissmissal.audit': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

## Admin Interface Implementation

Create a comprehensive admin interface in `dissmissal/admin.py`:

```python
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.utils import timezone
from .models import Student, PickupEvent

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    """Enhanced admin interface for student management"""
    
    list_display = [
        'name', 'dismissal_code', 'grade', 'teacher', 
        'current_status', 'status_updated_at', 'is_active'
    ]
    list_filter = [
        'is_active', 'current_status', 'grade', 'teacher', 'created_at'
    ]
    search_fields = ['name', 'dismissal_code', 'teacher']
    ordering = ['name']
    readonly_fields = ['dismissal_code', 'status_updated_at', 'created_at']
    
    fieldsets = (
        ('Student Information', {
            'fields': ('name', 'grade', 'teacher')
        }),
        ('Dismissal Details', {
            'fields': ('dismissal_code', 'current_status', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('status_updated_at', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['reset_to_waiting', 'deactivate_students', 'generate_new_codes']
    
    def reset_to_waiting(self, request, queryset):
        """Reset selected students to waiting status"""
        updated = queryset.update(current_status='WAITING')
        self.message_user(request, f'Reset {updated} students to waiting status.')
    reset_to_waiting.short_description = "Reset selected students to waiting"
    
    def deactivate_students(self, request, queryset):
        """Deactivate selected students"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'Deactivated {updated} students.')
    deactivate_students.short_description = "Deactivate selected students"


@admin.register(PickupEvent)
class PickupEventAdmin(admin.ModelAdmin):
    """Read-only audit interface for pickup events"""
    
    list_display = [
        'student', 'event_type', 'staff_member', 'timestamp', 
        'dismissal_code_used', 'ip_address'
    ]
    list_filter = [
        'event_type', 'timestamp', 'staff_member'
    ]
    search_fields = [
        'student__name', 'dismissal_code_used', 'staff_member__username',
        'staff_member__first_name', 'staff_member__last_name'
    ]
    ordering = ['-timestamp']
    
    # Make all fields read-only for audit integrity
    readonly_fields = [
        'student', 'staff_member', 'event_type', 'dismissal_code_used',
        'timestamp', 'notes', 'ip_address'
    ]
    
    def has_add_permission(self, request):
        """Events should only be created through the application"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Events should be immutable for audit integrity"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Events should never be deleted for compliance"""
        return False


# Customize the admin site
admin.site.site_header = "OpenDismissal Administration"
admin.site.site_title = "OpenDismissal Admin"
admin.site.index_title = "School Dismissal Management"
```

## Demo Data Management Command

Create `dissmissal/management/commands/generate_demo_data.py`:

```python
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from dissmissal.models import Student, PickupEvent
import random

class Command(BaseCommand):
    help = 'Generate demo data for OpenDismissal presentations and testing'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--students',
            type=int,
            default=25,
            help='Number of demo students to create (default: 25)'
        )
        parser.add_argument(
            '--events',
            action='store_true',
            help='Generate sample pickup events for realistic dashboard'
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Clear existing demo data before generating new data'
        )
    
    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Clearing existing demo data...')
            Student.objects.filter(name__startswith='Demo ').delete()
            PickupEvent.objects.filter(
                student__name__startswith='Demo '
            ).delete()
        
        # Create demo staff user
        demo_staff, created = User.objects.get_or_create(
            username='demo_staff',
            defaults={
                'first_name': 'Demo',
                'last_name': 'Staff',
                'email': 'demo@school.edu',
                'is_staff': True,
                'is_active': True
            }
        )
        if created:
            demo_staff.set_password('demo123')
            demo_staff.save()
            self.stdout.write(
                self.style.SUCCESS(f'Created demo staff user: {demo_staff.username}')
            )
        
        # Demo student data with realistic names and grades
        demo_students_data = [
            ('Demo Emma Johnson', '3rd', 'Mrs. Smith'),
            ('Demo Liam Chen', '4th', 'Mr. Davis'),
            ('Demo Olivia Williams', '2nd', 'Ms. Garcia'),
            ('Demo Noah Brown', '5th', 'Mrs. Wilson'),
            ('Demo Ava Rodriguez', '1st', 'Ms. Martinez'),
            ('Demo Ethan Miller', '3rd', 'Mrs. Smith'),
            ('Demo Sophia Anderson', '4th', 'Mr. Davis'),
            ('Demo Mason Taylor', '2nd', 'Ms. Garcia'),
            ('Demo Isabella Moore', '5th', 'Mrs. Wilson'),
            ('Demo Jacob White', '1st', 'Ms. Martinez'),
            ('Demo Charlotte Jones', '3rd', 'Mrs. Smith'),
            ('Demo William Garcia', '4th', 'Mr. Davis'),
            ('Demo Amelia Martinez', '2nd', 'Ms. Garcia'),
            ('Demo James Wilson', '5th', 'Mrs. Wilson'),
            ('Demo Harper Lopez', '1st', 'Ms. Martinez'),
            ('Demo Benjamin Lee', '3rd', 'Mrs. Smith'),
            ('Demo Evelyn Gonzalez', '4th', 'Mr. Davis'),
            ('Demo Lucas Hernandez', '2nd', 'Ms. Garcia'),
            ('Demo Abigail Perez', '5th', 'Mrs. Wilson'),
            ('Demo Henry Turner', '1st', 'Ms. Martinez'),
            ('Demo Emily Campbell', '3rd', 'Mrs. Smith'),
            ('Demo Alexander Parker', '4th', 'Mr. Davis'),
            ('Demo Elizabeth Evans', '2nd', 'Ms. Garcia'),
            ('Demo Sebastian Stewart', '5th', 'Mrs. Wilson'),
            ('Demo Scarlett Rivera', '1st', 'Ms. Martinez'),
        ]
        
        students_created = 0
        target_count = min(options['students'], len(demo_students_data))
        
        for i in range(target_count):
            name, grade, teacher = demo_students_data[i]
            
            # Create student with random status distribution
            status_choices = ['WAITING', 'PARENT_ARRIVED', 'PICKED_UP']
            status_weights = [0.6, 0.3, 0.1]  # Most waiting, some arrived, few picked up
            status = random.choices(status_choices, weights=status_weights)[0]
            
            student, created = Student.objects.get_or_create(
                name=name,
                defaults={
                    'grade': grade,
                    'teacher': teacher,
                    'current_status': status,
                    'is_active': True
                }
            )
            
            if created:
                students_created += 1
                self.stdout.write(f'Created: {student.name} ({student.dismissal_code})')
                
                # Generate sample events if requested
                if options['events'] and status != 'WAITING':
                    self.create_sample_events(student, demo_staff, status)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nDemo data generation complete!\n'
                f'Created {students_created} students\n'
                f'Demo staff login: demo_staff / demo123\n'
                f'Access admin at: /admin/\n'
                f'Access app at: /dissmissal/'
            )
        )
    
    def create_sample_events(self, student, staff_user, final_status):
        """Create realistic sample events for demonstration"""
        now = timezone.now()
        
        # Create parent arrival event (5-15 minutes ago)
        if final_status in ['PARENT_ARRIVED', 'PICKED_UP']:
            arrival_time = now - timedelta(minutes=random.randint(5, 15))
            PickupEvent.objects.create(
                student=student,
                staff_member=staff_user,
                event_type='PARENT_ARRIVED',
                dismissal_code_used=student.dismissal_code,
                timestamp=arrival_time,
                notes=f'Parent arrived for {student.name}',
                ip_address='127.0.0.1'
            )
        
        # Create pickup completion event (1-5 minutes ago)
        if final_status == 'PICKED_UP':
            pickup_time = now - timedelta(minutes=random.randint(1, 5))
            PickupEvent.objects.create(
                student=student,
                staff_member=staff_user,
                event_type='STUDENT_PICKED_UP',
                dismissal_code_used=student.dismissal_code,
                timestamp=pickup_time,
                notes=f'Pickup completed for {student.name}',
                ip_address='127.0.0.1'
            )
```

## Authentication & Basic API Setup

Create basic API endpoints in `dissmissal/api.py`:

```python
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.utils import timezone
from .models import Student, PickupEvent

@login_required
@require_http_methods(["GET"])
def dashboard_status_api(request):
    """
    Lightweight JSON endpoint for AJAX polling dashboard updates.
    Provides cached data for performance.
    """
    cache_key = f'dashboard_status_{request.user.id}'
    data = cache.get(cache_key)
    
    if not data:
        # Optimized query with select_related to prevent N+1
        students = Student.objects.select_related().filter(is_active=True)
        
        student_data = []
        for student in students:
            latest_event = student.get_latest_event()
            student_data.append({
                'id': student.id,
                'name': student.name,
                'dismissal_code': student.dismissal_code,
                'grade': student.grade,
                'teacher': student.teacher,
                'current_status': student.current_status,
                'status_display': student.get_current_status_display(),
                'last_updated': student.status_updated_at.isoformat() if student.status_updated_at else None,
                'latest_event': {
                    'type': latest_event.event_type if latest_event else None,
                    'timestamp': latest_event.timestamp.isoformat() if latest_event else None,
                    'staff': latest_event.staff_member.get_full_name() if latest_event else None,
                } if latest_event else None
            })
        
        # Dashboard statistics
        waiting_count = students.filter(current_status='WAITING').count()
        arrived_count = students.filter(current_status='PARENT_ARRIVED').count()
        picked_up_count = students.filter(current_status='PICKED_UP').count()
        
        data = {
            'students': student_data,
            'stats': {
                'total': len(student_data),
                'waiting': waiting_count,
                'parent_arrived': arrived_count,
                'picked_up': picked_up_count,
                'last_updated': timezone.now().isoformat()
            }
        }
        
        # Cache for 30 seconds to balance performance and freshness
        cache.set(cache_key, data, timeout=30)
    
    return JsonResponse(data)

@login_required 
@require_http_methods(["POST"])
def validate_dismissal_code_api(request):
    """
    AJAX endpoint for real-time dismissal code validation.
    Returns student info for valid codes.
    """
    dismissal_code = request.POST.get('code', '').upper().strip()
    
    if not dismissal_code:
        return JsonResponse({'valid': False, 'error': 'No code provided'})
    
    try:
        student = Student.objects.get(
            dismissal_code=dismissal_code,
            is_active=True
        )
        
        return JsonResponse({
            'valid': True,
            'student': {
                'id': student.id,
                'name': student.name,
                'grade': student.grade,
                'teacher': student.teacher,
                'current_status': student.current_status,
                'status_display': student.get_current_status_display()
            }
        })
        
    except Student.DoesNotExist:
        return JsonResponse({
            'valid': False, 
            'error': 'Invalid dismissal code'
        })
```

## URL Configuration

Create `dissmissal/urls.py`:

```python
from django.urls import path
from . import views, api

app_name = 'dissmissal'

urlpatterns = [
    # Main application views (will be implemented by Developer 2) 
    path('', views.dashboard_view, name='dashboard'),
    path('arrival/', views.parent_arrival_view, name='parent_arrival'),
    path('pickup/<int:student_id>/', views.student_pickup_view, name='student_pickup'),
    path('students/add/', views.add_student_view, name='add_student'),
    
    # API endpoints for AJAX functionality
    path('api/status/', api.dashboard_status_api, name='dashboard_status_api'),
    path('api/validate-code/', api.validate_dismissal_code_api, name='validate_code_api'),
]
```

Update `opendiss/urls.py`:

```python
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('dissmissal/', include('dissmissal.urls')),
    path('', lambda request: redirect('dissmissal:dashboard')),  # Redirect root to dashboard
]
```

## Testing Requirements

Create comprehensive tests in `dissmissal/tests/test_models.py`:

```python
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from dissmissal.models import Student, PickupEvent

class StudentModelTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='teststaff',
            email='test@school.edu',
            password='testpass123'
        )
    
    def test_student_creation_with_auto_code_generation(self):
        """Test student creation with automatic dismissal code generation"""
        student = Student.objects.create(
            name='Test Student',
            grade='3rd',
            teacher='Test Teacher'
        )
        
        self.assertIsNotNone(student.dismissal_code)
        self.assertEqual(len(student.dismissal_code), 6)
        self.assertTrue(student.dismissal_code.isalnum())
        self.assertTrue(student.dismissal_code.isupper())
    
    def test_dismissal_code_uniqueness(self):
        """Test that dismissal codes are unique across students"""
        student1 = Student.objects.create(
            name='Student 1',
            grade='1st', 
            teacher='Teacher 1'
        )
        student2 = Student.objects.create(
            name='Student 2',
            grade='2nd',
            teacher='Teacher 2'
        )
        
        self.assertNotEqual(student1.dismissal_code, student2.dismissal_code)
    
    def test_pickup_event_creation_and_status_update(self):
        """Test pickup event creation updates student status"""
        student = Student.objects.create(
            name='Test Student',
            grade='3rd',
            teacher='Test Teacher'
        )
        
        # Verify initial status
        self.assertEqual(student.current_status, 'WAITING')
        
        # Create parent arrival event
        event = PickupEvent.objects.create(
            student=student,
            staff_member=self.staff_user,
            event_type='PARENT_ARRIVED',
            dismissal_code_used=student.dismissal_code,
            ip_address='127.0.0.1'
        )
        
        # Verify status was updated
        student.refresh_from_db()
        self.assertEqual(student.current_status, 'PARENT_ARRIVED')
        
        # Create pickup completion event
        PickupEvent.objects.create(
            student=student,
            staff_member=self.staff_user,
            event_type='STUDENT_PICKED_UP',
            dismissal_code_used=student.dismissal_code,
            ip_address='127.0.0.1'
        )
        
        # Verify final status
        student.refresh_from_db()
        self.assertEqual(student.current_status, 'PICKED_UP')
    
    def test_student_manager_methods(self):
        """Test custom manager methods work correctly"""
        # Create test students with different statuses
        waiting_student = Student.objects.create(
            name='Waiting Student',
            grade='1st',
            teacher='Teacher 1',
            current_status='WAITING'
        )
        
        arrived_student = Student.objects.create(
            name='Arrived Student', 
            grade='2nd',
            teacher='Teacher 2',
            current_status='PARENT_ARRIVED'
        )
        
        picked_up_student = Student.objects.create(
            name='Picked Up Student',
            grade='3rd', 
            teacher='Teacher 3',
            current_status='PICKED_UP'
        )
        
        # Test waiting_for_pickup method
        waiting_students = Student.objects.waiting_for_pickup()
        self.assertEqual(waiting_students.count(), 2)  # WAITING + PARENT_ARRIVED
        self.assertIn(waiting_student, waiting_students)
        self.assertIn(arrived_student, waiting_students)
        self.assertNotIn(picked_up_student, waiting_students)
```

## Deliverables & Success Criteria

### Required Deliverables

1. **✅ Django Project Setup**
   - Complete project configuration with environment variables
   - Database configuration for PostgreSQL and SQLite
   - Redis caching configuration
   - Security middleware and logging setup

2. **✅ Core Models Implementation**
   - Student model with auto-generated dismissal codes
   - PickupEvent model with audit trail capabilities
   - Database indexes for performance optimization
   - Custom manager classes for query optimization

3. **✅ Admin Interface**
   - Comprehensive Student admin with actions
   - Read-only PickupEvent admin for audit integrity
   - Custom admin site branding

4. **✅ Demo Data Management**
   - Management command for generating realistic demo data
   - Sample students with various statuses
   - Sample pickup events for demonstration

5. **✅ Basic API Endpoints**
   - Dashboard status API for AJAX polling
   - Dismissal code validation API
   - Proper caching and performance optimization

6. **✅ Database Migrations**
   - Initial migration for core models
   - Database indexes for performance
   - Proper foreign key relationships

### Testing Checklist

- [ ] All models create and save correctly
- [ ] Dismissal code generation produces unique codes
- [ ] PickupEvent creation updates student status
- [ ] Database indexes improve query performance
- [ ] Admin interface displays correctly
- [ ] Demo data command generates realistic data
- [ ] API endpoints return proper JSON responses
- [ ] Caching works correctly

### Integration Points

**Dependencies for other developers:**
- Student and PickupEvent models must be completed first
- API endpoints provide data structure for frontend
- URL structure defines navigation for templates

**Integration with Developer 2:**
- Your models will be imported in their views.py
- Your API endpoints will be called by their business logic
- Your URL structure will be extended with their view functions

**Integration with Developer 3:**
- Your API endpoints provide data for their AJAX polling
- Your model field names determine their template variables
- Your admin interface styling affects their CSS approach

## Environment Setup

Create `.env` file template:

```env
# Django Configuration
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration
DATABASE_URL=sqlite:///db.sqlite3

# Redis Configuration (for caching)
REDIS_URL=redis://127.0.0.1:6379/1

# Timezone
TIME_ZONE=America/New_York
```

## Questions for Integration

Before proceeding, confirm these integration points:

1. **Model field naming:** Are the Student and PickupEvent field names clear for the other developers?
2. **API response format:** Does the JSON structure work for the frontend AJAX implementation?  
3. **URL namespace:** Is the 'dissmissal' namespace appropriate for the view URLs?
4. **Caching strategy:** Should cache keys include additional user context beyond user ID?
5. **Demo data:** What specific scenarios should the demo data cover for effective presentations?

---

**Next Steps:**
1. Set up development environment with PostgreSQL and Redis
2. Create Django project and implement models
3. Create and run initial migrations
4. Build admin interface and test with demo data
5. Implement API endpoints and test caching
6. Create comprehensive test suite
7. Document any integration questions for team discussion

Your foundation work enables the entire MVP - take time to get it right!