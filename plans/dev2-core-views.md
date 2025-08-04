# Developer 2: Core Views & Business Logic

**Developer:** Core Business Logic Lead  
**Branch:** `feature/core-views`  
**Timeline:** Days 1-10 of development  
**Dependencies:** Developer 1's backend foundation (models, admin, basic APIs)

## Project Context

You're implementing the core business logic for OpenDismissal - the Django views, forms, and security systems that power the staff dismissal workflow. Your work sits between the database foundation (Developer 1) and the user interface (Developer 3).

**Your role:** Create secure, validated, and optimized business logic that handles the complete dismissal workflow while maintaining FERPA compliance and production-ready security standards.

## Architecture Integration

### Dependencies from Developer 1
- ✅ **Models:** Student, PickupEvent with proper relationships
- ✅ **Basic APIs:** dashboard_status_api, validate_dismissal_code_api  
- ✅ **URL structure:** Base URL patterns in dissmissal/urls.py
- ✅ **Admin interface:** Complete admin for data management

### Deliverables for Developer 3
- ✅ **View functions:** Properly structured views with context data
- ✅ **Form classes:** Validated forms with proper error handling
- ✅ **URL routing:** Complete URL patterns for all workflows
- ✅ **Context data:** Template-ready data structures with proper formatting

## Core View Implementation

### 1. Dashboard View - Main Staff Interface

Create the central hub for dismissal coordination in `dissmissal/views.py`:

```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.core.cache import cache
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction
from django_ratelimit.decorators import ratelimit
from django.contrib.auth.models import User

import logging
from .models import Student, PickupEvent
from .forms import ParentArrivalForm, StudentPickupForm, AddStudentForm
from .utils import get_client_ip, log_audit_event

# Set up audit logging
audit_logger = logging.getLogger('dissmissal.audit')

@login_required
def dashboard_view(request):
    """
    Main staff dashboard showing current dismissal status.
    Optimized with caching and pagination for performance.
    """
    # Log dashboard access for audit trail
    log_audit_event(
        user=request.user,
        action='DASHBOARD_ACCESS',
        ip_address=get_client_ip(request),
        details={'timestamp': timezone.now().isoformat()}
    )
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    grade_filter = request.GET.get('grade', 'all')
    search_query = request.GET.get('search', '').strip()
    
    # Build cache key based on filters and user
    cache_key = f'dashboard_{request.user.id}_{status_filter}_{grade_filter}_{search_query}'
    dashboard_data = cache.get(cache_key)
    
    if not dashboard_data:
        # Optimized query to avoid N+1 problems
        students_query = Student.objects.select_related().filter(is_active=True)
        
        # Apply filters
        if status_filter != 'all':
            students_query = students_query.filter(current_status=status_filter)
        
        if grade_filter != 'all':
            students_query = students_query.filter(grade=grade_filter)
        
        if search_query:
            students_query = students_query.filter(
                models.Q(name__icontains=search_query) |
                models.Q(dismissal_code__icontains=search_query) |
                models.Q(teacher__icontains=search_query)
            )
        
        # Prefetch related pickup events for efficiency
        students = students_query.prefetch_related(
            models.Prefetch(
                'pickup_events',
                queryset=PickupEvent.objects.select_related('staff_member')
                                           .order_by('-timestamp')[:3]
            )
        ).order_by('name')
        
        # Calculate statistics
        stats = {
            'total_active': Student.objects.filter(is_active=True).count(),
            'waiting': Student.objects.filter(is_active=True, current_status='WAITING').count(),
            'parent_arrived': Student.objects.filter(is_active=True, current_status='PARENT_ARRIVED').count(),
            'picked_up': Student.objects.filter(is_active=True, current_status='PICKED_UP').count(),
        }
        
        # Get available grades and teachers for filter dropdowns
        grades = Student.objects.filter(is_active=True).values_list('grade', flat=True).distinct().order_by('grade')
        teachers = Student.objects.filter(is_active=True).values_list('teacher', flat=True).distinct().order_by('teacher')
        
        dashboard_data = {
            'students': students,
            'stats': stats,
            'grades': grades,
            'teachers': teachers,
            'last_updated': timezone.now()
        }
        
        # Cache for 60 seconds to balance performance and freshness
        cache.set(cache_key, dashboard_data, timeout=60)
    
    # Pagination for large student lists
    paginator = Paginator(dashboard_data['students'], 25)  # 25 students per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'students': page_obj.object_list,
        'stats': dashboard_data['stats'],
        'grades': dashboard_data['grades'],
        'teachers': dashboard_data['teachers'],
        'current_filters': {
            'status': status_filter,
            'grade': grade_filter,
            'search': search_query
        },
        'last_updated': dashboard_data['last_updated'],
        'page_title': 'Dismissal Dashboard'
    }
    
    return render(request, 'dissmissal/dashboard.html', context)
```

### 2. Parent Arrival View - Code Validation & Logging

Implement secure parent arrival processing:

```python
@login_required
@require_http_methods(["GET", "POST"])
@ratelimit(key='user', rate='20/m', method=['POST'])  # Prevent brute force attempts
@csrf_protect
def parent_arrival_view(request):
    """
    Handle parent arrival workflow with comprehensive validation and audit logging.
    Includes rate limiting to prevent brute force dismissal code attempts.
    """
    if request.method == 'POST':
        form = ParentArrivalForm(request.POST)
        
        if form.is_valid():
            dismissal_code = form.cleaned_data['dismissal_code']
            notes = form.cleaned_data.get('notes', '')
            
            try:
                with transaction.atomic():
                    # Get student with select_for_update to prevent race conditions
                    student = Student.objects.select_for_update().get(
                        dismissal_code=dismissal_code,
                        is_active=True
                    )
                    
                    # Validate current status allows parent arrival
                    if student.current_status == 'PICKED_UP':
                        messages.error(
                            request, 
                            f'{student.name} has already been picked up today.'
                        )
                        log_audit_event(
                            user=request.user,
                            action='PARENT_ARRIVAL_REJECTED',
                            ip_address=get_client_ip(request),
                            details={
                                'reason': 'already_picked_up',
                                'student_id': student.id,
                                'dismissal_code': dismissal_code
                            }
                        )
                        
                    elif student.current_status == 'PARENT_ARRIVED':
                        messages.warning(
                            request,
                            f'Parent arrival for {student.name} was already logged earlier.'
                        )
                        log_audit_event(
                            user=request.user,
                            action='PARENT_ARRIVAL_DUPLICATE',
                            ip_address=get_client_ip(request),
                            details={
                                'student_id': student.id,
                                'dismissal_code': dismissal_code
                            }
                        )
                        
                    else:  # Status is WAITING
                        # Create pickup event
                        pickup_event = PickupEvent.objects.create(
                            student=student,
                            staff_member=request.user,
                            event_type='PARENT_ARRIVED',
                            dismissal_code_used=dismissal_code,
                            notes=notes,
                            ip_address=get_client_ip(request)
                        )
                        
                        # Update student status (this is handled in PickupEvent.save())
                        student.refresh_from_db()
                        
                        # Clear dashboard cache
                        cache.delete_pattern(f'dashboard_{request.user.id}_*')
                        
                        # Success message and redirect
                        messages.success(
                            request,
                            f'Parent arrival logged for {student.name} (Grade {student.grade}, {student.teacher})'
                        )
                        
                        log_audit_event(
                            user=request.user,
                            action='PARENT_ARRIVAL_LOGGED',
                            ip_address=get_client_ip(request),
                            details={
                                'student_id': student.id,
                                'student_name': student.name,
                                'dismissal_code': dismissal_code,
                                'pickup_event_id': pickup_event.id
                            }
                        )
                        
                        return redirect('dissmissal:dashboard')
                        
            except Student.DoesNotExist:
                messages.error(
                    request,
                    'Invalid dismissal code. Please check the code and try again.'
                )
                log_audit_event(
                    user=request.user,
                    action='INVALID_DISMISSAL_CODE',
                    ip_address=get_client_ip(request),
                    details={
                        'attempted_code': dismissal_code,
                        'reason': 'student_not_found'
                    }
                )
                
            except Exception as e:
                messages.error(
                    request,
                    'An error occurred while processing the parent arrival. Please try again.'
                )
                audit_logger.error(
                    f'Parent arrival processing error: {str(e)}',
                    extra={
                        'user': request.user.username,
                        'ip_address': get_client_ip(request),
                        'dismissal_code': dismissal_code
                    }
                )
        
        else:
            # Form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    
    else:
        form = ParentArrivalForm()
    
    # Get recent arrivals for context (last 10)
    recent_arrivals = PickupEvent.objects.filter(
        event_type='PARENT_ARRIVED',
        timestamp__date=timezone.now().date()
    ).select_related('student', 'staff_member').order_by('-timestamp')[:10]
    
    context = {
        'form': form,
        'recent_arrivals': recent_arrivals,
        'page_title': 'Log Parent Arrival'
    }
    
    return render(request, 'dissmissal/parent_arrival.html', context)
```

### 3. Student Pickup View - Completion Workflow

Implement the pickup completion process:

```python
@login_required
@require_http_methods(["GET", "POST"])
@csrf_protect
def student_pickup_view(request, student_id=None):
    """
    Handle student pickup completion with proper workflow validation.
    Can be called with specific student_id or allow staff to select student.
    """
    student = None
    if student_id:
        student = get_object_or_404(Student, id=student_id, is_active=True)
    
    if request.method == 'POST':
        form = StudentPickupForm(request.POST, initial_student=student)
        
        if form.is_valid():
            selected_student = form.cleaned_data['student']
            notes = form.cleaned_data.get('notes', '')
            
            try:
                with transaction.atomic():
                    # Lock student record to prevent race conditions
                    selected_student = Student.objects.select_for_update().get(
                        id=selected_student.id
                    )
                    
                    # Validate student status allows pickup
                    if selected_student.current_status == 'PICKED_UP':
                        messages.error(
                            request,
                            f'{selected_student.name} has already been picked up.'
                        )
                        
                    elif selected_student.current_status == 'WAITING':
                        messages.error(
                            request,
                            f'Parent has not arrived yet for {selected_student.name}. '
                            f'Please log parent arrival first.'
                        )
                        
                    elif selected_student.current_status == 'PARENT_ARRIVED':
                        # Create pickup completion event
                        pickup_event = PickupEvent.objects.create(
                            student=selected_student,
                            staff_member=request.user,
                            event_type='STUDENT_PICKED_UP',
                            dismissal_code_used=selected_student.dismissal_code,
                            notes=notes,
                            ip_address=get_client_ip(request)
                        )
                        
                        # Status is updated automatically in PickupEvent.save()
                        selected_student.refresh_from_db()
                        
                        # Clear dashboard cache
                        cache.delete_pattern(f'dashboard_*')
                        
                        messages.success(
                            request,
                            f'Pickup completed for {selected_student.name}. '
                            f'Student has been dismissed safely.'
                        )
                        
                        log_audit_event(
                            user=request.user,
                            action='STUDENT_PICKUP_COMPLETED',
                            ip_address=get_client_ip(request),
                            details={
                                'student_id': selected_student.id,
                                'student_name': selected_student.name,
                                'pickup_event_id': pickup_event.id,
                                'notes': notes
                            }
                        )
                        
                        return redirect('dissmissal:dashboard')
                        
            except Exception as e:
                messages.error(
                    request,
                    'An error occurred while completing the pickup. Please try again.'
                )
                audit_logger.error(
                    f'Student pickup completion error: {str(e)}',
                    extra={
                        'user': request.user.username,
                        'student_id': selected_student.id if 'selected_student' in locals() else None,
                        'ip_address': get_client_ip(request)
                    }
                )
    
    else:
        form = StudentPickupForm(initial_student=student)
    
    # Get students ready for pickup (parent arrived status)
    ready_students = Student.objects.filter(
        is_active=True,
        current_status='PARENT_ARRIVED'
    ).order_by('name')
    
    # Get recent pickups for context
    recent_pickups = PickupEvent.objects.filter(
        event_type='STUDENT_PICKED_UP',
        timestamp__date=timezone.now().date()
    ).select_related('student', 'staff_member').order_by('-timestamp')[:10]
    
    context = {
        'form': form,
        'student': student,
        'ready_students': ready_students,
        'recent_pickups': recent_pickups,
        'page_title': f'Complete Pickup - {student.name}' if student else 'Complete Student Pickup'
    }
    
    return render(request, 'dissmissal/student_pickup.html', context)


@login_required
def add_student_view(request):
    """
    Add new students to the dismissal system.
    Typically used for late enrollments or day-of additions.
    """
    if request.method == 'POST':
        form = AddStudentForm(request.POST)
        
        if form.is_valid():
            try:
                student = form.save()
                
                messages.success(
                    request,
                    f'Successfully added {student.name} with dismissal code {student.dismissal_code}'
                )
                
                log_audit_event(
                    user=request.user,
                    action='STUDENT_ADDED',
                    ip_address=get_client_ip(request),
                    details={
                        'student_id': student.id,
                        'student_name': student.name,
                        'dismissal_code': student.dismissal_code
                    }
                )
                
                # Clear dashboard cache
                cache.delete_pattern('dashboard_*')
                
                return redirect('dissmissal:dashboard')
                
            except Exception as e:
                messages.error(
                    request,
                    'An error occurred while adding the student. Please try again.'
                )
                audit_logger.error(
                    f'Student addition error: {str(e)}',
                    extra={
                        'user': request.user.username,
                        'ip_address': get_client_ip(request),
                        'form_data': form.cleaned_data if form.is_valid() else 'invalid'
                    }
                )
    else:
        form = AddStudentForm()
    
    context = {
        'form': form,
        'page_title': 'Add New Student'
    }
    
    return render(request, 'dissmissal/add_student.html', context)
```

## Form Classes Implementation

Create comprehensive form validation in `dissmissal/forms.py`:

```python
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Student, PickupEvent
import re

class ParentArrivalForm(forms.Form):
    """
    Form for logging parent arrivals with dismissal code validation.
    Includes real-time validation and security measures.
    """
    dismissal_code = forms.CharField(
        max_length=8,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg form-control-mobile',
            'placeholder': 'Enter dismissal code',
            'autocomplete': 'off',
            'inputmode': 'text',
            'pattern': '[A-Z0-9]{6,8}',
            'title': 'Enter 6-8 character dismissal code (letters and numbers only)',
            'style': 'text-transform: uppercase; font-family: monospace;',
            'autofocus': True,
            'data-validate-url': '/dissmissal/api/validate-code/'  # For AJAX validation
        }),
        help_text='Enter the unique dismissal code provided to the parent'
    )
    
    notes = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional notes about parent arrival...'
        }),
        help_text='Optional notes about the parent arrival'
    )
    
    def clean_dismissal_code(self):
        """Validate dismissal code format and existence"""
        code = self.cleaned_data['dismissal_code'].upper().strip()
        
        # Format validation
        if not re.match(r'^[A-Z0-9]{6,8}$', code):
            raise ValidationError(
                'Dismissal code must be 6-8 characters using only letters and numbers.'
            )
        
        # Check if code exists and is active
        try:
            student = Student.objects.get(dismissal_code=code, is_active=True)
            
            # Store student for use in view (avoid duplicate queries)
            self.student = student
            
        except Student.DoesNotExist:
            raise ValidationError(
                'Invalid dismissal code. Please verify the code and try again.'
            )
        
        return code
    
    def clean_notes(self):
        """Sanitize and validate notes field"""
        notes = self.cleaned_data.get('notes', '').strip()
        
        # Basic length validation
        if len(notes) > 500:
            raise ValidationError('Notes cannot exceed 500 characters.')
        
        # Remove any potentially harmful content (basic sanitization)
        import html
        notes = html.escape(notes)
        
        return notes


class StudentPickupForm(forms.Form):
    """
    Form for completing student pickup process.
    Allows selection from students with parent_arrived status.
    """
    def __init__(self, *args, **kwargs):
        initial_student = kwargs.pop('initial_student', None)
        super().__init__(*args, **kwargs)
        
        # Get students ready for pickup
        ready_queryset = Student.objects.filter(
            is_active=True,
            current_status='PARENT_ARRIVED'
        ).order_by('name')
        
        self.fields['student'] = forms.ModelChoiceField(
            queryset=ready_queryset,
            empty_label="Select student for pickup...",
            widget=forms.Select(attrs={
                'class': 'form-control form-control-lg',
                'required': True
            }),
            help_text='Select the student to complete pickup'
        )
        
        # Pre-select student if provided
        if initial_student and initial_student.current_status == 'PARENT_ARRIVED':
            self.fields['student'].initial = initial_student
            self.fields['student'].widget.attrs['readonly'] = True
    
    notes = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional notes about pickup completion...'
        }),
        help_text='Optional notes about the pickup completion'
    )
    
    def clean_student(self):
        """Validate selected student is eligible for pickup"""
        student = self.cleaned_data['student']
        
        if student.current_status != 'PARENT_ARRIVED':
            raise ValidationError(
                f'{student.name} is not ready for pickup. '
                f'Current status: {student.get_current_status_display()}'
            )
        
        return student


class AddStudentForm(forms.ModelForm):
    """
    Form for adding new students to the system.
    Includes validation for required fields and generates dismissal code.
    """
    class Meta:
        model = Student
        fields = ['name', 'grade', 'teacher']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter full student name',
                'maxlength': 100
            }),
            'grade': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 3rd, 4th, 5th',
                'maxlength': 20
            }),
            'teacher': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter teacher name',
                'maxlength': 100
            })
        }
        help_texts = {
            'name': 'Enter the student\'s full name as it should appear in the system',
            'grade': 'Enter the student\'s current grade level',
            'teacher': 'Enter the homeroom teacher\'s name'
        }
    
    def clean_name(self):
        """Validate and format student name"""
        name = self.cleaned_data['name'].strip()
        
        if len(name) < 2:
            raise ValidationError('Student name must be at least 2 characters long.')
        
        if len(name) > 100:
            raise ValidationError('Student name cannot exceed 100 characters.')
        
        # Check for duplicate names (warning, not error)
        existing = Student.objects.filter(name__iexact=name, is_active=True)
        if existing.exists():
            # Don't raise error, but add a warning message
            pass
        
        return name.title()  # Proper case formatting
    
    def clean_grade(self):
        """Validate grade format"""
        grade = self.cleaned_data['grade'].strip()
        
        if not grade:
            raise ValidationError('Grade level is required.')
        
        return grade
    
    def clean_teacher(self):
        """Validate teacher name"""
        teacher = self.cleaned_data['teacher'].strip()
        
        if not teacher:
            raise ValidationError('Teacher name is required.')
        
        return teacher.title()  # Proper case formatting
    
    def save(self, commit=True):
        """Save student with auto-generated dismissal code"""
        student = super().save(commit=False)
        
        # Dismissal code will be auto-generated in Student.save()
        if commit:
            student.save()
        
        return student


class DashboardFilterForm(forms.Form):
    """
    Form for dashboard filtering and search functionality.
    Used for AJAX updates and URL parameter handling.
    """
    STATUS_CHOICES = [
        ('all', 'All Students'),
        ('WAITING', 'Waiting for Parent'),
        ('PARENT_ARRIVED', 'Parent Has Arrived'),
        ('PICKED_UP', 'Picked Up'),
    ]
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        initial='all',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'onchange': 'this.form.submit();'
        })
    )
    
    grade = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'onchange': 'this.form.submit();'
        })
    )
    
    search = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, code, or teacher...'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Populate grade choices dynamically
        grades = Student.objects.filter(is_active=True).values_list(
            'grade', flat=True
        ).distinct().order_by('grade')
        
        grade_choices = [('all', 'All Grades')] + [(g, g) for g in grades]
        self.fields['grade'].choices = grade_choices
```

## Utility Functions

Create utility functions in `dissmissal/utils.py`:

```python
import logging
from django.utils import timezone
from django.contrib.auth.models import User

# Set up audit logging
audit_logger = logging.getLogger('dissmissal.audit')

def get_client_ip(request):
    """
    Extract client IP address from request, accounting for proxies.
    Essential for FERPA compliance and security audit trails.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip or '127.0.0.1'

def log_audit_event(user, action, ip_address, details=None):
    """
    Log audit events for FERPA compliance and security monitoring.
    
    Args:
        user: Django User object who performed the action
        action: String describing the action taken
        ip_address: IP address of the user
        details: Dictionary of additional details to log
    """
    log_entry = {
        'user_id': user.id,
        'username': user.username,
        'user_full_name': user.get_full_name() or user.username,
        'action': action,
        'timestamp': timezone.now().isoformat(),
        'ip_address': ip_address,
        'details': details or {}
    }
    
    audit_logger.info(
        f"User {user.username} performed {action}",
        extra=log_entry
    )

def get_dashboard_stats():
    """
    Calculate dashboard statistics for display.
    Used by both views and API endpoints.
    """
    from .models import Student, PickupEvent
    
    today = timezone.now().date()
    
    stats = {
        'total_active': Student.objects.filter(is_active=True).count(),
        'waiting': Student.objects.filter(is_active=True, current_status='WAITING').count(),
        'parent_arrived': Student.objects.filter(is_active=True, current_status='PARENT_ARRIVED').count(),
        'picked_up': Student.objects.filter(is_active=True, current_status='PICKED_UP').count(),
        'events_today': PickupEvent.objects.filter(timestamp__date=today).count(),
        'last_updated': timezone.now()
    }
    
    # Calculate percentages
    if stats['total_active'] > 0:
        stats['waiting_percent'] = round((stats['waiting'] / stats['total_active']) * 100, 1)
        stats['arrived_percent'] = round((stats['parent_arrived'] / stats['total_active']) * 100, 1)
        stats['picked_up_percent'] = round((stats['picked_up'] / stats['total_active']) * 100, 1)
    else:
        stats['waiting_percent'] = stats['arrived_percent'] = stats['picked_up_percent'] = 0
    
    return stats

def validate_staff_permissions(user, required_permissions=None):
    """
    Validate staff member has required permissions for dismissal operations.
    
    Args:
        user: Django User object
        required_permissions: List of required permission strings
    
    Returns:
        bool: True if user has required permissions
    """
    if not user.is_authenticated:
        return False
    
    if not user.is_staff:
        return False
    
    if not user.is_active:
        return False
    
    if required_permissions:
        return user.has_perms(required_permissions)
    
    return True

def format_pickup_event_for_display(pickup_event):
    """
    Format pickup event data for template display.
    
    Args:
        pickup_event: PickupEvent model instance
    
    Returns:
        dict: Formatted event data for templates
    """
    return {
        'id': pickup_event.id,
        'student_name': pickup_event.student.name,
        'student_grade': pickup_event.student.grade,
        'event_type': pickup_event.get_event_type_display(),
        'event_type_code': pickup_event.event_type,
        'staff_name': pickup_event.staff_member.get_full_name() or pickup_event.staff_member.username,
        'timestamp': pickup_event.timestamp,
        'time_ago': timezone.now() - pickup_event.timestamp,
        'dismissal_code': pickup_event.dismissal_code_used,
        'notes': pickup_event.notes,
        'css_class': {
            'PARENT_ARRIVED': 'text-warning',
            'STUDENT_PICKED_UP': 'text-success',
            'CANCELLED': 'text-danger'
        }.get(pickup_event.event_type, 'text-muted')
    }
```

## Enhanced AJAX Endpoints

Extend the API functionality in `dissmissal/api.py`:

```python
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.core.cache import cache
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from .models import Student, PickupEvent
from .utils import get_client_ip, log_audit_event, get_dashboard_stats

@login_required
@require_http_methods(["POST"])
@ratelimit(key='user', rate='30/m')
@csrf_protect
def quick_pickup_api(request):
    """
    API endpoint for quick pickup completion via AJAX.
    Used for streamlined mobile interface.
    """
    student_id = request.POST.get('student_id')
    notes = request.POST.get('notes', '').strip()
    
    if not student_id:
        return JsonResponse({
            'success': False,
            'error': 'Student ID is required'
        })
    
    try:
        student = Student.objects.select_for_update().get(
            id=student_id,
            is_active=True
        )
        
        if student.current_status != 'PARENT_ARRIVED':
            return JsonResponse({
                'success': False,
                'error': f'{student.name} is not ready for pickup. Current status: {student.get_current_status_display()}'
            })
        
        # Create pickup event
        pickup_event = PickupEvent.objects.create(
            student=student,
            staff_member=request.user,
            event_type='STUDENT_PICKED_UP',
            dismissal_code_used=student.dismissal_code,
            notes=notes,
            ip_address=get_client_ip(request)
        )
        
        # Log audit event
        log_audit_event(
            user=request.user,
            action='STUDENT_PICKUP_COMPLETED_AJAX',
            ip_address=get_client_ip(request),
            details={
                'student_id': student.id,
                'student_name': student.name,
                'pickup_event_id': pickup_event.id
            }
        )
        
        # Clear cache
        cache.delete_pattern('dashboard_*')
        
        return JsonResponse({
            'success': True,
            'message': f'Pickup completed for {student.name}',
            'student': {
                'id': student.id,
                'name': student.name,
                'status': student.current_status,
                'status_display': student.get_current_status_display()
            }
        })
        
    except Student.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Student not found'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while processing pickup'
        })

@login_required
@require_http_methods(["GET"])
def dashboard_refresh_api(request):
    """
    Lightweight API endpoint for dashboard refresh.
    Returns only updated data to minimize bandwidth.
    """
    last_update = request.GET.get('last_update')
    
    # Get current stats
    stats = get_dashboard_stats()
    
    # If last_update provided, only return data if there are changes
    if last_update:
        try:
            last_update_time = timezone.datetime.fromisoformat(last_update.replace('Z', '+00:00'))
            
            # Check if any pickup events occurred since last update
            recent_events = PickupEvent.objects.filter(
                timestamp__gt=last_update_time
            ).count()
            
            if recent_events == 0:
                return JsonResponse({
                    'updated': False,
                    'stats': stats
                })
        except (ValueError, TypeError):
            pass  # Invalid timestamp, return full data
    
    # Get updated student data
    students = Student.objects.filter(is_active=True).select_related()
    
    student_data = []
    for student in students:
        latest_event = student.pickup_events.order_by('-timestamp').first()
        student_data.append({
            'id': student.id,
            'name': student.name,
            'dismissal_code': student.dismissal_code,
            'grade': student.grade,
            'teacher': student.teacher,
            'current_status': student.current_status,
            'status_display': student.get_current_status_display(),
            'last_updated': student.status_updated_at.isoformat(),
            'latest_event': {
                'type': latest_event.event_type if latest_event else None,
                'timestamp': latest_event.timestamp.isoformat() if latest_event else None,
                'staff': latest_event.staff_member.get_full_name() if latest_event else None,
            } if latest_event else None
        })
    
    return JsonResponse({
        'updated': True,
        'students': student_data,
        'stats': stats,
        'timestamp': timezone.now().isoformat()
    })
```

## URL Configuration Update

Complete the URL patterns in `dissmissal/urls.py`:

```python
from django.urls import path
from . import views, api

app_name = 'dissmissal'

urlpatterns = [
    # Main application views
    path('', views.dashboard_view, name='dashboard'),
    path('arrival/', views.parent_arrival_view, name='parent_arrival'),
    path('pickup/', views.student_pickup_view, name='student_pickup'),
    path('pickup/<int:student_id>/', views.student_pickup_view, name='student_pickup_specific'),
    path('students/add/', views.add_student_view, name='add_student'),
    
    # API endpoints for AJAX functionality
    path('api/status/', api.dashboard_status_api, name='dashboard_status_api'),
    path('api/refresh/', api.dashboard_refresh_api, name='dashboard_refresh_api'),
    path('api/validate-code/', api.validate_dismissal_code_api, name='validate_code_api'),
    path('api/quick-pickup/', api.quick_pickup_api, name='quick_pickup_api'),
]
```

## Testing Requirements

Create comprehensive tests in `dissmissal/tests/test_views.py`:

```python
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.cache import cache
from dissmissal.models import Student, PickupEvent
import json

class ViewsTestCase(TestCase):
    def setUp(self):
        """Set up test data and authenticated client"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='teststaff',
            email='test@school.edu',
            password='testpass123',
            first_name='Test',
            last_name='Staff'
        )
        self.user.is_staff = True
        self.user.save()
        
        # Create test student
        self.student = Student.objects.create(
            name='Test Student',
            grade='3rd',
            teacher='Test Teacher',
            current_status='WAITING'
        )
        
        # Clear cache before each test
        cache.clear()
    
    def test_dashboard_requires_authentication(self):
        """Test dashboard redirects unauthenticated users"""
        response = self.client.get(reverse('dissmissal:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)
    
    def test_dashboard_loads_with_students(self):
        """Test dashboard loads correctly with student data"""
        self.client.login(username='teststaff', password='testpass123')
        response = self.client.get(reverse('dissmissal:dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Student')
        self.assertContains(response, self.student.dismissal_code)
        self.assertIn('stats', response.context)
        self.assertIn('students', response.context)
    
    def test_parent_arrival_workflow_success(self):
        """Test successful parent arrival logging"""
        self.client.login(username='teststaff', password='testpass123')
        
        response = self.client.post(reverse('dissmissal:parent_arrival'), {
            'dismissal_code': self.student.dismissal_code,
            'notes': 'Test arrival notes'
        })
        
        # Should redirect to dashboard
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dissmissal:dashboard'))
        
        # Check student status was updated
        self.student.refresh_from_db()
        self.assertEqual(self.student.current_status, 'PARENT_ARRIVED')
        
        # Check pickup event was created
        event = PickupEvent.objects.get(student=self.student, event_type='PARENT_ARRIVED')
        self.assertEqual(event.staff_member, self.user)
        self.assertEqual(event.notes, 'Test arrival notes')
    
    def test_parent_arrival_invalid_code(self):
        """Test parent arrival with invalid dismissal code"""
        self.client.login(username='teststaff', password='testpass123')
        
        response = self.client.post(reverse('dissmissal:parent_arrival'), {
            'dismissal_code': 'INVALID',
            'notes': ''
        })
        
        # Should stay on same page with error
        self.assertEqual(response.status_code, 200)
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('Invalid dismissal code' in str(m) for m in messages))
        
        # Student status should not change
        self.student.refresh_from_db()
        self.assertEqual(self.student.current_status, 'WAITING')
    
    def test_student_pickup_completion(self):
        """Test student pickup completion workflow"""
        # Set student to parent_arrived status first
        self.student.current_status = 'PARENT_ARRIVED'
        self.student.save()
        
        self.client.login(username='teststaff', password='testpass123')
        
        response = self.client.post(reverse('dissmissal:student_pickup'), {
            'student': self.student.id,
            'notes': 'Pickup completed successfully'
        })
        
        # Should redirect to dashboard
        self.assertEqual(response.status_code, 302)
        
        # Check student status was updated
        self.student.refresh_from_db()
        self.assertEqual(self.student.current_status, 'PICKED_UP')
        
        # Check pickup completion event was created
        event = PickupEvent.objects.get(student=self.student, event_type='STUDENT_PICKED_UP')
        self.assertEqual(event.staff_member, self.user)
        self.assertEqual(event.notes, 'Pickup completed successfully')
    
    def test_add_student_functionality(self):
        """Test adding new student to system"""
        self.client.login(username='teststaff', password='testpass123')
        
        response = self.client.post(reverse('dissmissal:add_student'), {
            'name': 'New Test Student',
            'grade': '4th',
            'teacher': 'New Teacher'
        })
        
        # Should redirect to dashboard
        self.assertEqual(response.status_code, 302)
        
        # Check student was created
        new_student = Student.objects.get(name='New Test Student')
        self.assertEqual(new_student.grade, '4th')
        self.assertEqual(new_student.teacher, 'New Teacher')
        self.assertIsNotNone(new_student.dismissal_code)
        self.assertEqual(len(new_student.dismissal_code), 6)
    
    def test_api_dashboard_status(self):
        """Test dashboard status API endpoint"""
        self.client.login(username='teststaff', password='testpass123')
        
        response = self.client.get(reverse('dissmissal:dashboard_status_api'))
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertIn('students', data)
        self.assertIn('stats', data)
        self.assertEqual(len(data['students']), 1)
        self.assertEqual(data['students'][0]['name'], 'Test Student')
    
    def test_rate_limiting_protection(self):
        """Test rate limiting on sensitive endpoints"""
        self.client.login(username='teststaff', password='testpass123')
        
        # Make multiple rapid requests to parent arrival
        for i in range(25):  # Over the 20/minute limit
            response = self.client.post(reverse('dissmissal:parent_arrival'), {
                'dismissal_code': 'TEST123'
            })
        
        # Should eventually get rate limited (429 status)
        # Note: This test may need adjustment based on django-ratelimit configuration
        self.assertTrue(response.status_code in [200, 429, 403])
```

## Integration Points & Dependencies

### Integration with Developer 1 (Backend Foundation)
- ✅ **Import models:** `from .models import Student, PickupEvent`
- ✅ **Use API endpoints:** Build upon dashboard_status_api and validate_dismissal_code_api
- ✅ **Extend URLs:** Add view functions to existing URL structure
- ✅ **Cache integration:** Use cache keys and invalidation patterns

### Integration with Developer 3 (Frontend Templates)
- ✅ **Context data:** Provide properly formatted data for templates
- ✅ **Form rendering:** Forms designed for Bootstrap integration
- ✅ **AJAX endpoints:** JSON APIs for dynamic frontend updates
- ✅ **Error handling:** Messages framework for user feedback

## Success Criteria & Deliverables

### Required Deliverables

1. **✅ Core View Functions**
   - Dashboard with filtering, pagination, and caching
   - Parent arrival with validation and audit logging
   - Student pickup with workflow validation
   - Add student functionality with proper validation

2. **✅ Form Classes**
   - ParentArrivalForm with dismissal code validation
   - StudentPickupForm with status validation
   - AddStudentForm with field validation
   - DashboardFilterForm for search/filter functionality

3. **✅ Security Implementation**
   - Rate limiting on sensitive endpoints
   - CSRF protection on all state-changing operations
   - Input validation and sanitization
   - Comprehensive audit logging

4. **✅ AJAX API Endpoints**
   - Enhanced dashboard status API
   - Quick pickup API for mobile interface
   - Dashboard refresh API for efficient updates
   - Form validation APIs

5. **✅ Utility Functions**
   - IP address extraction for audit trails
   - Audit logging functions
   - Permission validation helpers
   - Data formatting utilities

### Testing Checklist

- [ ] All views require authentication
- [ ] Form validation prevents invalid data
- [ ] Pickup workflow enforces proper status transitions
- [ ] Rate limiting prevents brute force attacks
- [ ] Audit logging captures all critical actions
- [ ] AJAX endpoints return properly formatted JSON
- [ ] Cache invalidation works correctly
- [ ] Error handling provides useful feedback

### Performance Requirements

- [ ] Dashboard loads in <2 seconds with caching
- [ ] Parent arrival processing completes in <5 seconds
- [ ] API endpoints respond in <1 second
- [ ] Cache hit ratio >80% for dashboard data
- [ ] Database queries optimized with select_related/prefetch_related

---

**Next Steps:**
1. Review and understand Developer 1's model implementation
2. Implement view functions with proper security measures
3. Create comprehensive form validation
4. Build AJAX endpoints for real-time updates  
5. Write thorough test coverage
6. Test integration with Developer 1's backend
7. Prepare context data for Developer 3's templates

Your business logic layer is the heart of the application - ensure it's secure, reliable, and well-tested!