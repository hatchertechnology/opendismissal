"""
OpenDismissal Core Views

Core business logic views for the dismissal management system.
Author: Derek Hayes (Developer 2)
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.core.cache import cache
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction
from django_ratelimit.decorators import ratelimit
from django.db import models

import logging
from .models import Student, PickupEvent
from .forms import (
    ParentArrivalForm,
    StudentPickupForm,
    AddStudentForm,
    EditStudentForm,
    DashboardFilterForm,
)
from .utils import (
    get_client_ip,
    log_audit_event,
    get_dashboard_stats,
    generate_dashboard_cache_key,
    clear_dashboard_cache,
)

# Set up audit logging
audit_logger = logging.getLogger("dissmissal.audit")


# Helper functions for reducing view complexity


def _validate_student_status_for_arrival(student, request, dismissal_code):
    """
    Validate student status for parent arrival and handle appropriate responses.
    Returns True if arrival should be processed, False otherwise.
    """
    if student.current_status == "PICKED_UP":
        messages.error(request, f"{student.name} has already been picked up today.")
        log_audit_event(
            user=request.user,
            action="PARENT_ARRIVAL_REJECTED",
            ip_address=get_client_ip(request),
            details={
                "reason": "already_picked_up",
                "student_id": student.id,
                "dismissal_code": dismissal_code,
            },
        )
        return False

    if student.current_status == "PARENT_ARRIVED":
        messages.warning(
            request,
            f"Parent arrival for {student.name} was already logged earlier.",
        )
        log_audit_event(
            user=request.user,
            action="PARENT_ARRIVAL_DUPLICATE",
            ip_address=get_client_ip(request),
            details={"student_id": student.id, "dismissal_code": dismissal_code},
        )
        return False

    return True


def _process_parent_arrival(student, request, dismissal_code, notes):
    """
    Process successful parent arrival and create pickup event.
    Returns the created pickup event.
    """
    pickup_event = PickupEvent.objects.create(
        student=student,
        staff_member=request.user,
        event_type="PARENT_ARRIVED",
        dismissal_code_used=dismissal_code,
        notes=notes,
        ip_address=get_client_ip(request),
    )

    # Update student status (this is handled in PickupEvent.save())
    student.refresh_from_db()

    # Clear dashboard cache
    clear_dashboard_cache()

    # Success message and audit logging
    messages.success(
        request,
        f"Parent arrival logged for {student.name} (Grade {student.grade}, {student.teacher})",
    )

    log_audit_event(
        user=request.user,
        action="PARENT_ARRIVAL_LOGGED",
        ip_address=get_client_ip(request),
        details={
            "student_id": student.id,
            "student_name": student.name,
            "dismissal_code": dismissal_code,
            "pickup_event_id": pickup_event.id,
        },
    )

    return pickup_event


def _handle_invalid_dismissal_code(request, dismissal_code):
    """Handle invalid dismissal code attempts with proper error messaging and audit logging."""
    messages.error(request, "Invalid dismissal code. Please check the code and try again.")
    log_audit_event(
        user=request.user,
        action="INVALID_DISMISSAL_CODE",
        ip_address=get_client_ip(request),
        details={"attempted_code": dismissal_code, "reason": "student_not_found"},
    )


def _validate_student_status_for_pickup(student, request):
    """
    Validate student status for pickup completion and handle appropriate responses.
    Returns True if pickup should be processed, False otherwise.
    """
    if student.current_status == "PICKED_UP":
        messages.error(request, f"{student.name} has already been picked up.")
        return False

    if student.current_status == "WAITING":
        messages.error(
            request,
            f"Parent has not arrived yet for {student.name}. Please log parent arrival first.",
        )
        return False

    return student.current_status == "PARENT_ARRIVED"


def _process_student_pickup(student, request, notes):
    """
    Process student pickup completion and create pickup event.
    Returns the created pickup event.
    """
    pickup_event = PickupEvent.objects.create(
        student=student,
        staff_member=request.user,
        event_type="STUDENT_PICKED_UP",
        dismissal_code_used=student.dismissal_code,
        notes=notes,
        ip_address=get_client_ip(request),
    )

    # Status is updated automatically in PickupEvent.save()
    student.refresh_from_db()

    # Clear dashboard cache
    clear_dashboard_cache()

    messages.success(
        request,
        f"Pickup completed for {student.name}. Student has been dismissed safely.",
    )

    log_audit_event(
        user=request.user,
        action="STUDENT_PICKUP_COMPLETED",
        ip_address=get_client_ip(request),
        details={
            "student_id": student.id,
            "student_name": student.name,
            "pickup_event_id": pickup_event.id,
            "notes": notes,
        },
    )

    return pickup_event


@login_required
def dashboard_view(request):
    """
    Main staff dashboard showing current dismissal status.
    Optimized with caching and pagination for performance.
    """
    # Log dashboard access for audit trail
    log_audit_event(
        user=request.user,
        action="DASHBOARD_ACCESS",
        ip_address=get_client_ip(request),
        details={"timestamp": timezone.now().isoformat()},
    )

    # Get filter parameters
    status_filter = request.GET.get("status", "all")
    grade_filter = request.GET.get("grade", "all")
    search_query = request.GET.get("search", "").strip()

    # Build cache key based on filters and user
    cache_key = generate_dashboard_cache_key(
        user_id=request.user.id,
        status_filter=status_filter,
        grade_filter=grade_filter,
        search_query=search_query,
    )
    dashboard_data = cache.get(cache_key)

    if not dashboard_data:
        # Optimized query to avoid N+1 problems
        students_query = Student.objects.filter(is_active=True)

        # Apply filters
        if status_filter != "all":
            students_query = students_query.filter(current_status=status_filter)

        if grade_filter != "all":
            students_query = students_query.filter(grade=grade_filter)

        if search_query:
            students_query = students_query.filter(
                models.Q(name__icontains=search_query)
                | models.Q(dismissal_code__icontains=search_query)
                | models.Q(teacher__icontains=search_query)
            )

        # Prefetch related pickup events for efficiency
        students = students_query.prefetch_related(
            models.Prefetch(
                "pickup_events",
                queryset=PickupEvent.objects.select_related("staff_member").order_by("-timestamp"),
            )
        ).order_by("name")

        # Calculate statistics
        stats = get_dashboard_stats()

        # Get available grades and teachers for filter dropdowns
        grades = (
            Student.objects.filter(is_active=True)
            .values_list("grade", flat=True)
            .distinct()
            .order_by("grade")
        )
        teachers = (
            Student.objects.filter(is_active=True)
            .values_list("teacher", flat=True)
            .distinct()
            .order_by("teacher")
        )

        dashboard_data = {
            "students": students,
            "stats": stats,
            "grades": grades,
            "teachers": teachers,
            "last_updated": timezone.now(),
        }

        # Cache for 60 seconds to balance performance and freshness
        cache.set(cache_key, dashboard_data, timeout=60)

    # Pagination for large student lists
    paginator = Paginator(dashboard_data["students"], 25)  # 25 students per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Create filter form for template
    filter_form = DashboardFilterForm(
        initial={"status": status_filter, "grade": grade_filter, "search": search_query}
    )

    context = {
        "page_obj": page_obj,
        "students": page_obj.object_list,
        "stats": dashboard_data["stats"],
        "grades": dashboard_data["grades"],
        "teachers": dashboard_data["teachers"],
        "filter_form": filter_form,
        "current_filters": {"status": status_filter, "grade": grade_filter, "search": search_query},
        "last_updated": dashboard_data["last_updated"],
        "page_title": "Dismissal Dashboard",
    }

    return render(request, "dissmissal/dashboard.html", context)


@login_required
@require_http_methods(["GET", "POST"])
@ratelimit(key="user", rate="20/m", method=["POST"])  # Prevent brute force attempts
@csrf_protect
def parent_arrival_view(request, code=None):
    """
    Handle parent arrival workflow with comprehensive validation and audit logging.
    Includes rate limiting to prevent brute force dismissal code attempts.
    Accepts optional code parameter to pre-populate the dismissal code field.
    """
    if request.method == "POST":
        return _handle_parent_arrival_post(request)

    return _handle_parent_arrival_get(request, code)


def _handle_parent_arrival_post(request):
    """Handle POST request for parent arrival form submission."""
    form = ParentArrivalForm(request.POST)

    if not form.is_valid():
        _handle_form_validation_errors(request, form)
        return _render_parent_arrival_page(request, form)

    dismissal_code = form.cleaned_data["dismissal_code"]
    notes = form.cleaned_data.get("notes", "")

    try:
        with transaction.atomic():
            student = Student.objects.select_for_update().get(
                dismissal_code=dismissal_code, is_active=True
            )

            if not _validate_student_status_for_arrival(student, request, dismissal_code):
                return _render_parent_arrival_page(request, form)

            # Status is WAITING - process the arrival
            _process_parent_arrival(student, request, dismissal_code, notes)
            form = ParentArrivalForm()  # Clear form for next entry

    except Student.DoesNotExist:
        _handle_invalid_dismissal_code(request, dismissal_code)
    except Exception as e:
        _handle_arrival_processing_error(request, e, dismissal_code)

    return _render_parent_arrival_page(request, form)


def _handle_parent_arrival_get(request, code):
    """Handle GET request for parent arrival form display."""
    initial_data = {}
    if code:
        initial_data["dismissal_code"] = code.upper()

    form = ParentArrivalForm(initial=initial_data)
    return _render_parent_arrival_page(request, form)


def _handle_form_validation_errors(request, form):
    """Handle form validation errors by adding error messages."""
    for field, errors in form.errors.items():
        for error in errors:
            messages.error(request, f"{field}: {error}")


def _handle_arrival_processing_error(request, exception, dismissal_code):
    """Handle unexpected errors during parent arrival processing."""
    messages.error(
        request,
        "An error occurred while processing the parent arrival. Please try again.",
    )
    audit_logger.error(
        f"Parent arrival processing error: {str(exception)}",
        extra={
            "user": request.user.username,
            "ip_address": get_client_ip(request),
            "dismissal_code": dismissal_code,
        },
    )


def _render_parent_arrival_page(request, form):
    """Render the parent arrival page with context data."""
    recent_arrivals = (
        PickupEvent.objects.filter(
            event_type="PARENT_ARRIVED", timestamp__date=timezone.now().date()
        )
        .select_related("student", "staff_member")
        .order_by("-timestamp")[:10]
    )

    context = {"form": form, "recent_arrivals": recent_arrivals, "page_title": "Log Parent Arrival"}

    return render(request, "dissmissal/parent_arrival.html", context)


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

    if request.method == "POST":
        return _handle_student_pickup_post(request, student)

    return _handle_student_pickup_get(request, student)


def _handle_student_pickup_post(request, initial_student):
    """Handle POST request for student pickup form submission."""
    form = StudentPickupForm(request.POST, initial_student=initial_student)

    if not form.is_valid():
        return _render_student_pickup_page(request, form, initial_student)

    selected_student = form.cleaned_data["student"]
    notes = form.cleaned_data.get("notes", "")

    try:
        with transaction.atomic():
            # Lock student record to prevent race conditions
            selected_student = Student.objects.select_for_update().get(id=selected_student.id)

            if not _validate_student_status_for_pickup(selected_student, request):
                return _render_student_pickup_page(request, form, initial_student)

            # Status is PARENT_ARRIVED - process the pickup
            _process_student_pickup(selected_student, request, notes)
            return redirect("dissmissal:dashboard")

    except Exception as e:
        _handle_pickup_processing_error(request, e, selected_student)

    return _render_student_pickup_page(request, form, initial_student)


def _handle_student_pickup_get(request, student):
    """Handle GET request for student pickup form display."""
    form = StudentPickupForm(initial_student=student)
    return _render_student_pickup_page(request, form, student)


def _handle_pickup_processing_error(request, exception, student):
    """Handle unexpected errors during student pickup processing."""
    messages.error(request, "An error occurred while completing the pickup. Please try again.")
    audit_logger.error(
        f"Student pickup completion error: {str(exception)}",
        extra={
            "user": request.user.username,
            "student_id": student.id if student else None,
            "ip_address": get_client_ip(request),
        },
    )


def _render_student_pickup_page(request, form, student):
    """Render the student pickup page with context data."""
    # Get students ready for pickup (parent arrived status)
    ready_students = Student.objects.filter(
        is_active=True, current_status="PARENT_ARRIVED"
    ).order_by("name")

    # Get recent pickups for context
    recent_pickups = (
        PickupEvent.objects.filter(
            event_type="STUDENT_PICKED_UP", timestamp__date=timezone.now().date()
        )
        .select_related("student", "staff_member")
        .order_by("-timestamp")[:10]
    )

    context = {
        "form": form,
        "student": student,
        "ready_students": ready_students,
        "recent_pickups": recent_pickups,
        "page_title": f"Complete Pickup - {student.name}" if student else "Complete Student Pickup",
    }

    return render(request, "dissmissal/student_pickup.html", context)


@login_required
@require_http_methods(["GET", "POST"])
@csrf_protect
def add_student_view(request):
    """
    Add new students to the dismissal system.
    Typically used for late enrollments or day-of additions.
    """
    if request.method == "POST":
        form = AddStudentForm(request.POST)

        if form.is_valid():
            try:
                student = form.save()

                messages.success(
                    request,
                    f"Successfully added {student.name} with dismissal code {student.dismissal_code}",
                )

                log_audit_event(
                    user=request.user,
                    action="STUDENT_ADDED",
                    ip_address=get_client_ip(request),
                    details={
                        "student_id": student.id,
                        "student_name": student.name,
                        "dismissal_code": student.dismissal_code,
                    },
                )

                # Clear dashboard cache
                clear_dashboard_cache()

                return redirect("dissmissal:dashboard")

            except Exception as e:
                messages.error(
                    request, "An error occurred while adding the student. Please try again."
                )
                audit_logger.error(
                    f"Student addition error: {str(e)}",
                    extra={
                        "user": request.user.username,
                        "ip_address": get_client_ip(request),
                        "form_data": form.cleaned_data if form.is_valid() else "invalid",
                    },
                )
    else:
        form = AddStudentForm()

    context = {"form": form, "page_title": "Add New Student"}

    return render(request, "dissmissal/add_student.html", context)


@login_required
@require_http_methods(["GET", "POST"])
@csrf_protect
def student_details_view(request, student_id):
    """
    View and edit student details.
    Allows updating student information and viewing pickup history.
    """
    student = get_object_or_404(Student, id=student_id)

    if request.method == "POST":
        form = EditStudentForm(request.POST, instance=student)

        if form.is_valid():
            try:
                # Track what fields changed
                original_values = {}
                for field in form.changed_data:
                    original_values[field] = getattr(student, field)

                updated_student = form.save()

                # Log the changes
                log_audit_event(
                    user=request.user,
                    action="STUDENT_UPDATED",
                    ip_address=get_client_ip(request),
                    details={
                        "student_id": student.id,
                        "student_name": student.name,
                        "changed_fields": form.changed_data,
                        "original_values": original_values,
                    },
                )

                messages.success(
                    request,
                    f"Successfully updated {updated_student.name}'s information",
                )

                # Clear dashboard cache
                clear_dashboard_cache()

                return redirect("dissmissal:student_details", student_id=student.id)

            except Exception as e:
                messages.error(
                    request, "An error occurred while updating the student. Please try again."
                )
                audit_logger.error(
                    f"Student update error: {str(e)}",
                    extra={
                        "user": request.user.username,
                        "student_id": student.id,
                        "ip_address": get_client_ip(request),
                    },
                )
    else:
        form = EditStudentForm(instance=student)

    # Get student's pickup history
    pickup_events = student.pickup_events.select_related("staff_member").order_by("-timestamp")[:20]

    context = {
        "form": form,
        "student": student,
        "pickup_events": pickup_events,
        "page_title": f"Student Details - {student.name}",
    }

    return render(request, "dissmissal/student_details.html", context)


# Mobile Interface Views


@login_required
def greeter_mobile_view(request):
    """
    Ultra-simple mobile greeter interface for parent arrival check-in.
    Designed for outdoor use with large touch targets and minimal UI.
    """
    # Log mobile interface access
    log_audit_event(
        user=request.user,
        action="MOBILE_GREETER_ACCESS",
        ip_address=get_client_ip(request),
        details={"timestamp": timezone.now().isoformat()},
    )

    context = {
        "page_title": "Parent Check-in",
        "user_name": request.user.get_full_name() or request.user.username,
    }
    return render(request, "dissmissal/greeter.html", context)


@login_required
def releaser_mobile_view(request):
    """
    Ultra-simple mobile releaser interface for student pickup completion.
    Shows queue of students ready for pickup with tap-to-complete.
    """
    # Log mobile interface access
    log_audit_event(
        user=request.user,
        action="MOBILE_RELEASER_ACCESS",
        ip_address=get_client_ip(request),
        details={"timestamp": timezone.now().isoformat()},
    )

    context = {
        "page_title": "Student Release",
        "user_name": request.user.get_full_name() or request.user.username,
    }
    return render(request, "dissmissal/releaser.html", context)
