"""
OpenDismissal Models

Core models for the dismissal management system.
Author: Derek Hayes (Developer 2) & Elena Rodriguez (Developer 1)
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .constants import (
    STUDENT_NAME_MAX_LENGTH,
    TEACHER_NAME_MAX_LENGTH,
    GRADE_MAX_LENGTH,
    STATUS_MAX_LENGTH,
    EVENT_TYPE_MAX_LENGTH,
    DISMISSAL_CODE_MAX_LENGTH,
    DISMISSAL_CODE_START_VALUE,
)


class StudentManager(models.Manager):
    """Custom manager for optimized student queries"""

    def active_with_events(self):
        """Active students with prefetched latest events"""
        return self.filter(is_active=True).prefetch_related(
            models.Prefetch(
                "pickup_events",
                queryset=PickupEvent.objects.select_related("staff_member").order_by("-timestamp"),
            )
        )

    def waiting_for_pickup(self):
        """Students waiting for parent or ready for pickup"""
        return self.active_with_events().filter(current_status__in=["WAITING", "PARENT_ARRIVED"])

    def by_grade(self, grade):
        """Filter students by grade level"""
        return self.active_with_events().filter(grade=grade)


class Student(models.Model):
    """
    Student model with embedded dismissal code for simplified architecture.
    Includes status tracking optimization for dashboard performance.
    Tracks student dismissal status using STATUS_CHOICES for efficient dashboard queries.
    Enhanced validation methods ensure data integrity for dismissal codes and status updates.
    """

    STATUS_CHOICES = [
        ("WAITING", "Waiting for Parent"),
        ("PARENT_ARRIVED", "Parent Has Arrived"),
        ("PICKED_UP", "Student Picked Up"),
    ]

    # Core student information
    name = models.CharField(max_length=STUDENT_NAME_MAX_LENGTH, help_text="Student's full name")
    dismissal_code = models.CharField(
        max_length=DISMISSAL_CODE_MAX_LENGTH,
        unique=True,
        db_index=True,
        blank=True,  # Allow blank for auto-generation
        help_text=f"Unique 1-{DISMISSAL_CODE_MAX_LENGTH} character alphanumeric code for parent verification. Leave blank to auto-generate starting at {DISMISSAL_CODE_START_VALUE}.",
    )
    grade = models.CharField(max_length=GRADE_MAX_LENGTH, help_text="Student's grade level")
    teacher = models.CharField(max_length=TEACHER_NAME_MAX_LENGTH, help_text="Homeroom teacher name")

    # Status tracking
    is_active = models.BooleanField(default=True, help_text="Active in current dismissal")
    current_status = models.CharField(
        max_length=STATUS_MAX_LENGTH,
        choices=STATUS_CHOICES,
        default="WAITING",
        db_index=True,
        help_text="Current dismissal status for quick dashboard queries",
    )
    status_updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Add the custom manager
    objects = StudentManager()

    class Meta:
        indexes = [
            models.Index(fields=["dismissal_code"]),
            models.Index(fields=["is_active", "current_status"]),
            models.Index(fields=["grade", "teacher"]),
            models.Index(fields=["-created_at"]),  # For admin ordering
        ]
        ordering = ["name"]
        verbose_name = "Student"
        verbose_name_plural = "Students"

    def __str__(self):
        return f"{self.name} ({self.dismissal_code}) - {self.get_current_status_display()}"

    def clean(self):
        """Validate student data including dismissal code"""
        from .utils import validate_and_format_dismissal_code, check_dismissal_code_uniqueness
        
        if not self.name or len(self.name.strip()) < 2:
            raise ValidationError("Student name must be at least 2 characters long")

        if not self.grade or not self.grade.strip():
            raise ValidationError("Grade level is required")

        if not self.teacher or not self.teacher.strip():
            raise ValidationError("Teacher name is required")
        
        # Validate dismissal code if provided
        if self.dismissal_code:
            formatted_code, is_valid, error_message = validate_and_format_dismissal_code(
                self.dismissal_code, allow_empty=False
            )
            if not is_valid:
                raise ValidationError({"dismissal_code": error_message})
            
            # Check uniqueness
            is_unique, error_message = check_dismissal_code_uniqueness(
                formatted_code, exclude_student_id=self.pk
            )
            if not is_unique:
                raise ValidationError({"dismissal_code": error_message})
            
            # Apply formatting
            self.dismissal_code = formatted_code

    def save(self, *args, **kwargs):
        """Auto-generate dismissal code if not provided and validate data"""
        # Generate dismissal code if not provided (before validation)
        if not self.dismissal_code:
            self.dismissal_code = self.generate_dismissal_code()

        # Format names properly
        self.name = self.name.strip().title()
        self.teacher = self.teacher.strip().title()
        self.grade = self.grade.strip()

        # Validate after setting required fields
        self.full_clean()

        super().save(*args, **kwargs)
        
        # Log dismissal code changes for audit trail
        # Note: This requires request context, which we'll handle in the admin
        # For now, we'll just track the change without logging

    @classmethod
    def generate_dismissal_code(cls):
        f"""Generate unique incrementing dismissal code starting at {DISMISSAL_CODE_START_VALUE}"""
        # Find the highest numeric dismissal code that's >= DISMISSAL_CODE_START_VALUE
        existing_codes = cls.objects.filter(
            dismissal_code__regex=r'^[0-9]+$',
            dismissal_code__gte=str(DISMISSAL_CODE_START_VALUE)
        ).values_list('dismissal_code', flat=True)
        
        # Convert to integers and find the maximum
        numeric_codes = []
        for code in existing_codes:
            try:
                num = int(code)
                if num >= DISMISSAL_CODE_START_VALUE:  # Only consider codes >= DISMISSAL_CODE_START_VALUE for auto-increment
                    numeric_codes.append(num)
            except ValueError:
                continue
        
        if numeric_codes:
            next_code = max(numeric_codes) + 1
        else:
            next_code = DISMISSAL_CODE_START_VALUE  # Start at DISMISSAL_CODE_START_VALUE
        
        # Ensure the generated code doesn't conflict with any existing code
        while cls.objects.filter(dismissal_code=str(next_code)).exists():
            next_code += 1
        
        return str(next_code)
    
    def update_dismissal_code(self, new_code, user=None, ip_address=None, method="manual"):
        """Update dismissal code with audit logging"""
        from .utils import log_dismissal_code_change
        
        old_code = self.dismissal_code
        
        if new_code:
            # Manual code update
            self.dismissal_code = new_code
        else:
            # Auto-generate new code
            self.dismissal_code = self.generate_dismissal_code()
            method = "auto_generated"
        
        # Save with validation
        self.save()
        
        # Log the change if user and IP are provided
        if user and ip_address:
            log_dismissal_code_change(
                user=user,
                student=self,
                old_code=old_code,
                new_code=self.dismissal_code,
                ip_address=ip_address,
                method=method
            )
        
        return self.dismissal_code

    def get_latest_event(self):
        """Get most recent pickup event for this student"""
        return self.pickup_events.order_by("-timestamp").first()

    def get_today_events(self):
        """Get all pickup events for today"""
        from django.utils import timezone

        today = timezone.now().date()
        return self.pickup_events.filter(timestamp__date=today).order_by("-timestamp")

class PickupEvent(models.Model):
    """
    Event-driven audit trail for all dismissal actions.
    Provides immutable history for FERPA compliance.
    """

    EVENT_TYPE_CHOICES = [
        ("PARENT_ARRIVED", "Parent Arrived"),
        ("STUDENT_PICKED_UP", "Student Picked Up"),
        ("CANCELLED", "Pickup Cancelled"),
    ]

    # Core event information
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="pickup_events",
        help_text="Student this event relates to",
    )
    staff_member = models.ForeignKey(
        User,
        on_delete=models.PROTECT,  # Protect from accidental staff deletion
        help_text="Staff member who performed this action",
    )
    event_type = models.CharField(
        max_length=EVENT_TYPE_MAX_LENGTH, choices=EVENT_TYPE_CHOICES, help_text="Type of dismissal event"
    )

    # Audit information
    dismissal_code_used = models.CharField(
        max_length=DISMISSAL_CODE_MAX_LENGTH, help_text="The dismissal code that was used for verification"
    )
    timestamp = models.DateTimeField(auto_now_add=True, help_text="When this event occurred")
    notes = models.TextField(blank=True, help_text="Optional notes about this event")
    ip_address = models.GenericIPAddressField(
        help_text="IP address of the staff member when event occurred"
    )

    class Meta:
        indexes = [
            models.Index(fields=["student", "-timestamp"]),
            models.Index(fields=["event_type", "-timestamp"]),
            models.Index(fields=["staff_member", "-timestamp"]),
            models.Index(fields=["-timestamp"]),  # For general event queries
        ]
        ordering = ["-timestamp"]
        verbose_name = "Pickup Event"
        verbose_name_plural = "Pickup Events"

    def __str__(self):
        return f"{self.student.name} - {self.get_event_type_display()} by {self.staff_member.get_full_name() or self.staff_member.username}"

    def clean(self):
        """Validate event data"""
        if not self.dismissal_code_used:
            raise ValidationError("Dismissal code is required")

        if not self.ip_address:
            raise ValidationError("IP address is required for audit trail")

    def save(self, *args, **kwargs):
        """Update student status when pickup events are created"""
        self.full_clean()

        # Save the event first
        super().save(*args, **kwargs)

        # Update student's current status based on this event
        if self.event_type == "PARENT_ARRIVED":
            self.student.current_status = "PARENT_ARRIVED"
            self.student.save(update_fields=["current_status", "status_updated_at"])
        elif self.event_type == "STUDENT_PICKED_UP":
            self.student.current_status = "PICKED_UP"
            self.student.save(update_fields=["current_status", "status_updated_at"])
        elif self.event_type == "CANCELLED":
            self.student.current_status = "WAITING"
            self.student.save(update_fields=["current_status", "status_updated_at"])
