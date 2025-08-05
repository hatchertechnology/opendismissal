"""
OpenDismissal Admin Configuration

Admin interface for managing students and pickup events.
Author: Derek Hayes (Developer 2) & Elena Rodriguez (Developer 1)
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Student, PickupEvent


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    """Enhanced admin interface for student management with visual enhancements and bulk actions"""

    list_display = [
        "name",
        "dismissal_code_display",
        "grade",
        "teacher",
        "current_status_badge",
        "status_updated_at",
        "is_active",
    ]
    list_filter = ["is_active", "current_status", "grade", "teacher", "created_at"]
    search_fields = ["name", "dismissal_code", "teacher"]
    ordering = ["name"]
    readonly_fields = ["status_updated_at", "created_at"]

    fieldsets = (
        ("Student Information", {"fields": ("name", "grade", "teacher")}),
        ("Dismissal Details", {"fields": ("dismissal_code", "current_status", "is_active")}),
        ("Timestamps", {"fields": ("status_updated_at", "created_at"), "classes": ("collapse",)}),
    )

    actions = ["reset_to_waiting", "deactivate_students", "generate_new_codes"]

    def save_model(self, request, obj, form, change):
        """Add user context for audit logging"""
        from .utils import get_client_ip
        obj._change_user = request.user
        obj._change_ip = get_client_ip(request)
        super().save_model(request, obj, form, change)

    def dismissal_code_display(self, obj):
        """Display dismissal code with monospace font"""
        return format_html(
            '<code style="font-family: monospace; font-weight: bold;">{}</code>', obj.dismissal_code
        )

    dismissal_code_display.short_description = "Dismissal Code"

    def current_status_badge(self, obj):
        """Display status with color-coded badge"""
        colors = {
            "WAITING": "#ffc107",  # Yellow
            "PARENT_ARRIVED": "#17a2b8",  # Blue
            "PICKED_UP": "#28a745",  # Green
        }
        color = colors.get(obj.current_status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_current_status_display(),
        )

    current_status_badge.short_description = "Status"

    def get_queryset(self, request):
        """Optimize queryset to reduce database queries"""
        return super().get_queryset(request).select_related()

    def reset_to_waiting(self, request, queryset):
        """Reset selected students to waiting status"""
        updated = queryset.update(current_status="WAITING")
        self.message_user(request, f"Reset {updated} students to waiting status.")

    reset_to_waiting.short_description = "Reset selected students to waiting"

    def deactivate_students(self, request, queryset):
        """Deactivate selected students"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {updated} students.")

    deactivate_students.short_description = "Deactivate selected students"

    def generate_new_codes(self, request, queryset):
        """Generate new dismissal codes for selected students"""
        count = 0
        for student in queryset:
            student.dismissal_code = Student.generate_dismissal_code()
            student.save(update_fields=["dismissal_code"])
            count += 1
        self.message_user(request, f"Generated new codes for {count} students.")

    generate_new_codes.short_description = "Generate new dismissal codes"


@admin.register(PickupEvent)
class PickupEventAdmin(admin.ModelAdmin):
    """Read-only audit interface for pickup events with visual enhancements"""

    list_display = [
        "timestamp",
        "student_link",
        "event_type_badge",
        "staff_member_display",
        "dismissal_code_used",
        "ip_address",
    ]
    list_filter = ["event_type", "timestamp", "staff_member"]
    search_fields = [
        "student__name",
        "student__dismissal_code",
        "staff_member__username",
        "staff_member__first_name",
        "staff_member__last_name",
        "dismissal_code_used",
    ]
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]

    # Make all fields read-only for audit integrity
    readonly_fields = [
        "student",
        "staff_member",
        "event_type",
        "dismissal_code_used",
        "timestamp",
        "ip_address",
        "notes",
    ]

    fieldsets = [
        ("Event Details", {"fields": ["student", "event_type", "timestamp"]}),
        ("Staff Information", {"fields": ["staff_member", "dismissal_code_used"]}),
        ("Audit Trail", {"fields": ["ip_address", "notes"]}),
    ]

    def student_link(self, obj):
        """Display student name as link to student admin page"""
        url = reverse("admin:dissmissal_student_change", args=[obj.student.pk])
        return format_html('<a href="{}">{}</a>', url, obj.student.name)

    student_link.short_description = "Student"

    def staff_member_display(self, obj):
        """Display staff member with full name if available"""
        full_name = obj.staff_member.get_full_name()
        if full_name:
            return f"{full_name} ({obj.staff_member.username})"
        return obj.staff_member.username

    staff_member_display.short_description = "Staff Member"

    def event_type_badge(self, obj):
        """Display event type with color-coded badge"""
        colors = {
            "PARENT_ARRIVED": "#17a2b8",  # Blue
            "STUDENT_PICKED_UP": "#28a745",  # Green
            "CANCELLED": "#dc3545",  # Red
        }
        color = colors.get(obj.event_type, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_event_type_display(),
        )

    event_type_badge.short_description = "Event Type"

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related("student", "staff_member")

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
