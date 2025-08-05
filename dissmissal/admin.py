"""
OpenDismissal Admin Configuration

Admin interface for managing students and pickup events.
Author: Derek Hayes (Developer 2) & Elena Rodriguez (Developer 1)
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from .models import Student, PickupEvent
import csv
import io




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


class DismissalCodesAdminMixin:
    """Mixin to add CSV import/export functionality for dismissal codes"""
    
    def get_urls(self):
        """Add custom URLs for CSV operations"""
        urls = super().get_urls()
        custom_urls = [
            path(
                'bulk-import-dismissal-codes/',
                self.admin_site.admin_view(self.bulk_import_dismissal_codes_view),
                name='bulk_import_dismissal_codes',
            ),
            path(
                'export-dismissal-codes/',
                self.admin_site.admin_view(self.export_dismissal_codes_view),
                name='export_dismissal_codes',
            ),
        ]
        return custom_urls + urls
    
    def bulk_import_dismissal_codes_view(self, request):
        """Handle CSV import of dismissal codes"""
        from .utils import log_dismissal_code_change, get_client_ip, validate_and_format_dismissal_code, clear_dashboard_cache
        
        if request.method == 'POST':
            csv_file = request.FILES.get('csv_file')
            if not csv_file:
                messages.error(request, "Please select a CSV file.")
                return render(request, 'admin/bulk_import_dismissal_codes.html')
            
            if not csv_file.name.endswith('.csv'):
                messages.error(request, "File must be a CSV file.")
                return render(request, 'admin/bulk_import_dismissal_codes.html')
            
            try:
                # Read CSV file
                file_data = csv_file.read().decode('utf-8')
                csv_reader = csv.DictReader(io.StringIO(file_data))
                
                required_fields = ['student_name', 'dismissal_code']
                if not all(field in csv_reader.fieldnames for field in required_fields):
                    messages.error(request, f"CSV must contain columns: {', '.join(required_fields)}")
                    return render(request, 'admin/bulk_import_dismissal_codes.html')
                
                success_count = 0
                error_count = 0
                errors = []
                ip_address = get_client_ip(request)
                
                for row_num, row in enumerate(csv_reader, start=2):
                    student_name = row.get('student_name', '').strip()
                    new_code = row.get('dismissal_code', '').strip()
                    
                    if not student_name:
                        errors.append(f"Row {row_num}: Student name is required")
                        error_count += 1
                        continue
                    
                    # Find student by name
                    try:
                        student = Student.objects.get(name__iexact=student_name)
                    except Student.DoesNotExist:
                        errors.append(f"Row {row_num}: Student '{student_name}' not found")
                        error_count += 1
                        continue
                    except Student.MultipleObjectsReturned:
                        errors.append(f"Row {row_num}: Multiple students found with name '{student_name}'")
                        error_count += 1
                        continue
                    
                    # Validate dismissal code
                    if new_code:
                        formatted_code, is_valid, error_message = validate_and_format_dismissal_code(new_code)
                        if not is_valid:
                            errors.append(f"Row {row_num}: {error_message}")
                            error_count += 1
                            continue
                        
                        # Check uniqueness
                        if Student.objects.filter(dismissal_code=formatted_code).exclude(id=student.id).exists():
                            errors.append(f"Row {row_num}: Code '{formatted_code}' is already in use")
                            error_count += 1
                            continue
                    else:
                        formatted_code = Student.generate_dismissal_code()
                    
                    # Update student code
                    old_code = student.dismissal_code
                    student.dismissal_code = formatted_code
                    student.save()
                    
                    # Log the change
                    log_dismissal_code_change(
                        user=request.user,
                        student=student,
                        old_code=old_code,
                        new_code=formatted_code,
                        ip_address=ip_address,
                        method="csv_import"
                    )
                    
                    success_count += 1
                
                # Show results
                if success_count > 0:
                    clear_dashboard_cache()  # Clear cache after successful imports
                    messages.success(request, f"Successfully updated {success_count} dismissal codes.")
                
                if error_count > 0:
                    error_message = f"{error_count} errors occurred:\n" + "\n".join(errors[:10])
                    if len(errors) > 10:
                        error_message += f"\n... and {len(errors) - 10} more errors"
                    messages.error(request, error_message)
                
                if success_count > 0 and error_count == 0:
                    return redirect('admin:dissmissal_student_changelist')
                    
            except Exception as e:
                messages.error(request, f"Error processing CSV file: {str(e)}")
        
        # Show upload form
        context = {
            'title': 'Bulk Import Dismissal Codes',
            'opts': Student._meta,
        }
        return render(request, 'admin/bulk_import_dismissal_codes.html', context)
    
    def export_dismissal_codes_view(self, request):
        """Export all dismissal codes as CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="dismissal_codes.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['student_name', 'dismissal_code', 'grade', 'teacher', 'current_status'])
        
        for student in Student.objects.filter(is_active=True).order_by('name'):
            writer.writerow([
                student.name,
                student.dismissal_code, 
                student.grade,
                student.teacher,
                student.get_current_status_display()
            ])
        
        return response


# Register Student admin with enhanced functionality


@admin.register(Student)
@method_decorator(never_cache, name='changelist_view')
@method_decorator(never_cache, name='change_view')
@method_decorator(never_cache, name='add_view')
class StudentAdmin(DismissalCodesAdminMixin, admin.ModelAdmin):
    """Enhanced admin interface for student management with dismissal code editing and bulk operations"""

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
        ("Dismissal Details", {
            "fields": ("dismissal_code", "current_status", "is_active"),
            "description": "Leave dismissal code blank to auto-generate starting at 100. Manual codes must be 1-8 characters (letters and numbers only)."
        }),
        ("Timestamps", {"fields": ("status_updated_at", "created_at"), "classes": ("collapse",)}),
    )

    actions = [
        "reset_to_waiting", 
        "deactivate_students", 
        "generate_new_codes",
        "bulk_update_codes_csv"
    ]

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
        """Get fresh queryset without caching - always fetch latest data"""
        # Don't use select_related() to avoid potential caching issues
        # Force a fresh query every time to ensure latest data in admin
        return Student.objects.all().order_by('name')
    
    def changelist_view(self, request, extra_context=None):
        """Override changelist view to add no-cache headers"""
        response = super().changelist_view(request, extra_context)
        
        # Add cache control headers to prevent any caching
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        
        return response
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Override change view to add no-cache headers"""
        response = super().change_view(request, object_id, form_url, extra_context)
        
        # Add cache control headers to prevent any caching
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache' 
        response['Expires'] = '0'
        
        return response
    
    def add_view(self, request, form_url='', extra_context=None):
        """Override add view to add no-cache headers"""
        response = super().add_view(request, form_url, extra_context)
        
        # Add cache control headers to prevent any caching
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        
        return response

    def reset_to_waiting(self, request, queryset):
        """Reset selected students to waiting status"""
        from .utils import clear_dashboard_cache
        
        updated = queryset.update(current_status="WAITING")
        clear_dashboard_cache()  # Clear cache after status change
        self.message_user(request, f"Reset {updated} students to waiting status.")

    reset_to_waiting.short_description = "Reset selected students to waiting"

    def deactivate_students(self, request, queryset):
        """Deactivate selected students"""
        from .utils import clear_dashboard_cache
        
        updated = queryset.update(is_active=False)
        clear_dashboard_cache()  # Clear cache after deactivation
        self.message_user(request, f"Deactivated {updated} students.")

    deactivate_students.short_description = "Deactivate selected students"

    def generate_new_codes(self, request, queryset):
        """Generate new dismissal codes for selected students"""
        from .utils import log_dismissal_code_change, get_client_ip, clear_dashboard_cache
        
        count = 0
        ip_address = get_client_ip(request)
        
        for student in queryset:
            old_code = student.dismissal_code
            student.dismissal_code = Student.generate_dismissal_code()
            student.save(update_fields=["dismissal_code"])
            
            # Log the change
            log_dismissal_code_change(
                user=request.user,
                student=student,
                old_code=old_code,
                new_code=student.dismissal_code,
                ip_address=ip_address,
                method="admin_bulk_generate"
            )
            count += 1
        
        clear_dashboard_cache()  # Clear cache after bulk code generation
        self.message_user(request, f"Generated new codes for {count} students.")

    generate_new_codes.short_description = "Generate new dismissal codes"
    
    def bulk_update_codes_csv(self, request, queryset):
        """Redirect to CSV import page for bulk code updates"""
        from django.shortcuts import redirect
        from django.urls import reverse
        
        # Store selected student IDs in session for CSV import
        selected_ids = list(queryset.values_list('id', flat=True))
        request.session['bulk_update_student_ids'] = selected_ids
        
        # Redirect to CSV import page
        return redirect(reverse('admin:bulk_import_dismissal_codes'))
    
    bulk_update_codes_csv.short_description = "Bulk update codes via CSV"
    
    def save_model(self, request, obj, form, change):
        """Override save to log dismissal code changes and clear cache"""
        from .utils import log_dismissal_code_change, get_client_ip, clear_dashboard_cache
        
        old_code = None
        old_status = None
        if change:
            try:
                old_student = Student.objects.get(pk=obj.pk)
                old_code = old_student.dismissal_code
                old_status = old_student.current_status
            except Student.DoesNotExist:
                pass
        
        super().save_model(request, obj, form, change)
        
        # Log dismissal code changes
        if old_code != obj.dismissal_code:
            log_dismissal_code_change(
                user=request.user,
                student=obj,
                old_code=old_code,
                new_code=obj.dismissal_code,
                ip_address=get_client_ip(request),
                method="admin_edit"
            )
        
        # Clear dashboard cache if student data changed
        if (old_code != obj.dismissal_code or 
            old_status != obj.current_status or 
            not change):  # New student
            clear_dashboard_cache()


# Remove the old StudentAdmin registration since we're re-registering with new functionality

# Customize the admin site
admin.site.site_header = "OpenDismissal Administration"
admin.site.site_title = "OpenDismissal Admin"
admin.site.index_title = "School Dismissal Management"
