from django.contrib import admin
from .models import Student, PickupEvent


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    """Enhanced admin interface for student management"""

    list_display = [
        "name",
        "dismissal_code",
        "grade",
        "teacher",
        "current_status",
        "status_updated_at",
        "is_active",
    ]
    list_filter = ["is_active", "current_status", "grade", "teacher", "created_at"]
    search_fields = ["name", "dismissal_code", "teacher"]
    ordering = ["name"]
    readonly_fields = ["dismissal_code", "status_updated_at", "created_at"]

    fieldsets = (
        ("Student Information", {"fields": ("name", "grade", "teacher")}),
        ("Dismissal Details", {"fields": ("dismissal_code", "current_status", "is_active")}),
        ("Timestamps", {"fields": ("status_updated_at", "created_at"), "classes": ("collapse",)}),
    )

    actions = ["reset_to_waiting", "deactivate_students", "generate_new_codes"]

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
    """Read-only audit interface for pickup events"""

    list_display = [
        "student",
        "event_type",
        "staff_member",
        "timestamp",
        "dismissal_code_used",
        "ip_address",
    ]
    list_filter = ["event_type", "timestamp", "staff_member"]
    search_fields = [
        "student__name",
        "dismissal_code_used",
        "staff_member__username",
        "staff_member__first_name",
        "staff_member__last_name",
    ]
    ordering = ["-timestamp"]

    # Make all fields read-only for audit integrity
    readonly_fields = [
        "student",
        "staff_member",
        "event_type",
        "dismissal_code_used",
        "timestamp",
        "notes",
        "ip_address",
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
