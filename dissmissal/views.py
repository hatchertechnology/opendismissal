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
from .forms import ParentArrivalForm, StudentPickupForm, AddStudentForm, DashboardFilterForm
from .utils import (
    get_client_ip,
    log_audit_event,
    get_dashboard_stats,
    generate_dashboard_cache_key,
    clear_dashboard_cache,
)

# Set up audit logging
audit_logger = logging.getLogger("dissmissal.audit")


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
        students_query = Student.objects.select_related().filter(is_active=True)

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
def parent_arrival_view(request):
    """
    Handle parent arrival workflow with comprehensive validation and audit logging.
    Includes rate limiting to prevent brute force dismissal code attempts.
    """
    if request.method == "POST":
        form = ParentArrivalForm(request.POST)

        if form.is_valid():
            dismissal_code = form.cleaned_data["dismissal_code"]
            notes = form.cleaned_data.get("notes", "")

            try:
                with transaction.atomic():
                    # Get student with select_for_update to prevent race conditions
                    student = Student.objects.select_for_update().get(
                        dismissal_code=dismissal_code, is_active=True
                    )

                    # Validate current status allows parent arrival
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

                    elif student.current_status == "PARENT_ARRIVED":
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

                    else:  # Status is WAITING
                        # Create pickup event
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

                        # Success message and redirect
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

                        return redirect("dissmissal:dashboard")

            except Student.DoesNotExist:
                messages.error(
                    request, "Invalid dismissal code. Please check the code and try again."
                )
                log_audit_event(
                    user=request.user,
                    action="INVALID_DISMISSAL_CODE",
                    ip_address=get_client_ip(request),
                    details={"attempted_code": dismissal_code, "reason": "student_not_found"},
                )

            except Exception as e:
                messages.error(
                    request,
                    "An error occurred while processing the parent arrival. Please try again.",
                )
                audit_logger.error(
                    f"Parent arrival processing error: {str(e)}",
                    extra={
                        "user": request.user.username,
                        "ip_address": get_client_ip(request),
                        "dismissal_code": dismissal_code,
                    },
                )

        else:
            # Form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

    else:
        form = ParentArrivalForm()

    # Get recent arrivals for context (last 10)
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
        form = StudentPickupForm(request.POST, initial_student=student)

        if form.is_valid():
            selected_student = form.cleaned_data["student"]
            notes = form.cleaned_data.get("notes", "")

            try:
                with transaction.atomic():
                    # Lock student record to prevent race conditions
                    selected_student = Student.objects.select_for_update().get(
                        id=selected_student.id
                    )

                    # Validate student status allows pickup
                    if selected_student.current_status == "PICKED_UP":
                        messages.error(
                            request, f"{selected_student.name} has already been picked up."
                        )

                    elif selected_student.current_status == "WAITING":
                        messages.error(
                            request,
                            f"Parent has not arrived yet for {selected_student.name}. "
                            f"Please log parent arrival first.",
                        )

                    elif selected_student.current_status == "PARENT_ARRIVED":
                        # Create pickup completion event
                        pickup_event = PickupEvent.objects.create(
                            student=selected_student,
                            staff_member=request.user,
                            event_type="STUDENT_PICKED_UP",
                            dismissal_code_used=selected_student.dismissal_code,
                            notes=notes,
                            ip_address=get_client_ip(request),
                        )

                        # Status is updated automatically in PickupEvent.save()
                        selected_student.refresh_from_db()

                        # Clear dashboard cache
                        clear_dashboard_cache()

                        messages.success(
                            request,
                            f"Pickup completed for {selected_student.name}. "
                            f"Student has been dismissed safely.",
                        )

                        log_audit_event(
                            user=request.user,
                            action="STUDENT_PICKUP_COMPLETED",
                            ip_address=get_client_ip(request),
                            details={
                                "student_id": selected_student.id,
                                "student_name": selected_student.name,
                                "pickup_event_id": pickup_event.id,
                                "notes": notes,
                            },
                        )

                        return redirect("dissmissal:dashboard")

            except Exception as e:
                messages.error(
                    request, "An error occurred while completing the pickup. Please try again."
                )
                audit_logger.error(
                    f"Student pickup completion error: {str(e)}",
                    extra={
                        "user": request.user.username,
                        "student_id": selected_student.id
                        if "selected_student" in locals()
                        else None,
                        "ip_address": get_client_ip(request),
                    },
                )

    else:
        form = StudentPickupForm(initial_student=student)

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
