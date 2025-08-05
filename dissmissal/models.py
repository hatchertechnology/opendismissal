"""
OpenDismissal Models

Core models for the dismissal management system.
Author: Derek Hayes (Developer 2) & Elena Rodriguez (Developer 1)
"""

import secrets
import string
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


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
    """

    STATUS_CHOICES = [
        ("WAITING", "Waiting for Parent"),
        ("PARENT_ARRIVED", "Parent Has Arrived"),
        ("PICKED_UP", "Student Picked Up"),
    ]

    # Core student information
    name = models.CharField(max_length=100, help_text="Student's full name")
    dismissal_code = models.CharField(
        max_length=8,
        unique=True,
        db_index=True,
        help_text="Unique 6-8 character code for parent verification",
    )
    grade = models.CharField(max_length=20, help_text="Student's grade level")
    teacher = models.CharField(max_length=100, help_text="Homeroom teacher name")

    # Status tracking
    is_active = models.BooleanField(default=True, help_text="Active in current dismissal")
    current_status = models.CharField(
        max_length=20,
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
        """Validate student data"""
        if not self.name or len(self.name.strip()) < 2:
            raise ValidationError("Student name must be at least 2 characters long")

        if not self.grade or not self.grade.strip():
            raise ValidationError("Grade level is required")

        if not self.teacher or not self.teacher.strip():
            raise ValidationError("Teacher name is required")

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

    @classmethod
    def generate_dismissal_code(cls):
        """Generate cryptographically secure unique dismissal code"""
        while True:
            # Use secrets module for cryptographic security
            code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            if not cls.objects.filter(dismissal_code=code).exists():
                return code

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
        max_length=20, choices=EVENT_TYPE_CHOICES, help_text="Type of dismissal event"
    )

    # Audit information
    dismissal_code_used = models.CharField(
        max_length=8, help_text="The dismissal code that was used for verification"
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
