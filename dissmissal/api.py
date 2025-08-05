"""
OpenDismissal AJAX API Endpoints

API endpoints for real-time functionality and AJAX interactions.
Author: Derek Hayes (Developer 2) & Elena Rodriguez (Developer 1)
"""

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.core.cache import cache
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from django.db import transaction, models

from .models import Student, PickupEvent
from .utils import get_client_ip, log_audit_event, get_dashboard_stats
import json


@login_required
@require_http_methods(["GET"])
def dashboard_status_api(request):
    """
    Lightweight JSON endpoint for AJAX polling dashboard updates.
    Provides cached data for performance with comprehensive error handling.
    """
    try:
        cache_key = f"dashboard_status_{request.user.id}"
        data = cache.get(cache_key)

        if not data:
            # Optimized query with select_related to prevent N+1
            students = Student.objects.select_related().filter(is_active=True)

            student_data = []
            for student in students:
                latest_event = student.get_latest_event()
                student_data.append(
                    {
                        "id": student.id,
                        "name": student.name,
                        "dismissal_code": student.dismissal_code,
                        "grade": student.grade,
                        "teacher": student.teacher,
                        "current_status": student.current_status,
                        "status_display": student.get_current_status_display(),
                        "status_updated_at": student.status_updated_at.isoformat(),
                        "latest_event": {
                            "type": latest_event.event_type if latest_event else None,
                            "timestamp": latest_event.timestamp.isoformat() if latest_event else None,
                            "staff": latest_event.staff_member.get_full_name()
                            if latest_event
                            else None,
                        }
                        if latest_event
                        else None,
                    }
                )

            # Get current statistics
            stats = get_dashboard_stats()

            data = {
                "success": True,
                "students": student_data,
                "stats": stats,
                "timestamp": timezone.now().isoformat(),
            }

            # Cache for 5 seconds to match dashboard refresh rate
            cache.set(cache_key, data, timeout=5)

        response = JsonResponse(data)
        # Prevent caching of real-time data
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

    except Exception:
        response = JsonResponse(
            {"success": False, "error": "Failed to retrieve dashboard status"}, status=500
        )
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response


@login_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="30/m")
@csrf_protect
def validate_dismissal_code_api(request):
    """
    AJAX endpoint for real-time dismissal code validation.
    Returns student info for valid codes with rate limiting.
    """
    try:
        # Support both JSON and form data for flexibility
        if request.content_type == "application/json":
            data = json.loads(request.body)
            dismissal_code = data.get("dismissal_code", "").upper().strip()
        else:
            dismissal_code = request.POST.get("code", "").upper().strip()

        if not dismissal_code:
            return JsonResponse({"valid": False, "error": "Dismissal code is required"})

        # Validate format
        from .utils import validate_dismissal_code_format

        is_valid_format, format_error = validate_dismissal_code_format(dismissal_code)

        if not is_valid_format:
            return JsonResponse({"valid": False, "error": format_error})

        # Check if student exists and is active
        try:
            student = Student.objects.get(dismissal_code=dismissal_code, is_active=True)

            return JsonResponse(
                {
                    "valid": True,
                    "student": {
                        "id": student.id,
                        "name": student.name,
                        "grade": student.grade,
                        "teacher": student.teacher,
                        "current_status": student.current_status,
                        "status_display": student.get_current_status_display(),
                    },
                }
            )

        except Student.DoesNotExist:
            return JsonResponse({"valid": False, "error": "Invalid dismissal code"})

    except json.JSONDecodeError:
        return JsonResponse({"valid": False, "error": "Invalid request format"})
    except Exception:
        return JsonResponse({"valid": False, "error": "Validation error occurred"})


@login_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="30/m")
@csrf_protect
def quick_pickup_api(request):
    """
    API endpoint for quick pickup completion via AJAX.
    Used for streamlined mobile interface.
    """
    try:
        data = json.loads(request.body)
        student_id = data.get("student_id")
        notes = data.get("notes", "").strip()

        if not student_id:
            return JsonResponse({"success": False, "error": "Student ID is required"})

        with transaction.atomic():
            try:
                student = Student.objects.select_for_update().get(id=student_id, is_active=True)
            except Student.DoesNotExist:
                return JsonResponse({"success": False, "error": "Student not found"})

            if student.current_status != "PARENT_ARRIVED":
                return JsonResponse(
                    {
                        "success": False,
                        "error": f"{student.name} is not ready for pickup. Current status: {student.get_current_status_display()}",
                    }
                )

            # Create pickup event
            pickup_event = PickupEvent.objects.create(
                student=student,
                staff_member=request.user,
                event_type="STUDENT_PICKED_UP",
                dismissal_code_used=student.dismissal_code,
                notes=notes,
                ip_address=get_client_ip(request),
            )

            # Log audit event
            log_audit_event(
                user=request.user,
                action="STUDENT_PICKUP_COMPLETED_AJAX",
                ip_address=get_client_ip(request),
                details={
                    "student_id": student.id,
                    "student_name": student.name,
                    "pickup_event_id": pickup_event.id,
                },
            )

            # Clear cache
            from .utils import clear_dashboard_cache

            clear_dashboard_cache()

            # Refresh student data
            student.refresh_from_db()

            response = JsonResponse(
                {
                    "success": True,
                    "message": f"Pickup completed for {student.name}",
                    "student": {
                        "id": student.id,
                        "name": student.name,
                        "status": student.current_status,
                        "status_display": student.get_current_status_display(),
                    },
                }
            )
            # Prevent caching of pickup responses
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            return response

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid request format"})
    except Exception:
        return JsonResponse(
            {"success": False, "error": "An error occurred while processing pickup"}
        )


@login_required
@require_http_methods(["GET"])
def dashboard_refresh_api(request):
    """
    Lightweight API endpoint for dashboard refresh.
    Returns only updated data to minimize bandwidth.
    """
    last_update = request.GET.get("last_update")

    try:
        # Get current stats
        stats = get_dashboard_stats()

        # If last_update provided, only return data if there are changes
        if last_update:
            try:
                last_update_time = timezone.datetime.fromisoformat(
                    last_update.replace("Z", "+00:00")
                )

                # Check if any pickup events occurred since last update
                recent_events = PickupEvent.objects.filter(timestamp__gt=last_update_time).count()

                if recent_events == 0:
                    return JsonResponse({"updated": False, "stats": stats})
            except (ValueError, TypeError):
                pass  # Invalid timestamp, return full data

        # Get updated student data
        students = Student.objects.filter(is_active=True).select_related()

        student_data = []
        for student in students:
            latest_event = student.pickup_events.order_by("-timestamp").first()
            student_data.append(
                {
                    "id": student.id,
                    "name": student.name,
                    "dismissal_code": student.dismissal_code,
                    "grade": student.grade,
                    "teacher": student.teacher,
                    "current_status": student.current_status,
                    "status_display": student.get_current_status_display(),
                    "last_updated": student.status_updated_at.isoformat(),
                    "latest_event": {
                        "type": latest_event.event_type if latest_event else None,
                        "timestamp": latest_event.timestamp.isoformat() if latest_event else None,
                        "staff": latest_event.staff_member.get_full_name()
                        if latest_event
                        else None,
                    }
                    if latest_event
                    else None,
                }
            )

        return JsonResponse(
            {
                "updated": True,
                "students": student_data,
                "stats": stats,
                "timestamp": timezone.now().isoformat(),
            }
        )

    except Exception:
        return JsonResponse({"success": False, "error": "Failed to refresh dashboard"}, status=500)


@login_required
@require_http_methods(["GET"])
def student_search_api(request):
    """
    API endpoint for student search with autocomplete functionality.
    """
    query = request.GET.get("q", "").strip()
    limit = min(int(request.GET.get("limit", 10)), 50)  # Max 50 results

    if len(query) < 2:
        return JsonResponse({"results": [], "message": "Please enter at least 2 characters"})

    try:
        # Search students by name, dismissal code, or teacher
        students = Student.objects.filter(
            models.Q(name__icontains=query)
            | models.Q(dismissal_code__icontains=query)
            | models.Q(teacher__icontains=query),
            is_active=True,
        ).select_related()[:limit]

        results = []
        for student in students:
            results.append(
                {
                    "id": student.id,
                    "name": student.name,
                    "dismissal_code": student.dismissal_code,
                    "grade": student.grade,
                    "teacher": student.teacher,
                    "current_status": student.current_status,
                    "status_display": student.get_current_status_display(),
                }
            )

        return JsonResponse({"results": results, "count": len(results)})

    except Exception:
        return JsonResponse({"results": [], "error": "Search failed"})


@login_required
@require_http_methods(["POST"])
@csrf_protect
def bulk_action_api(request):
    """
    API endpoint for bulk actions on multiple students.
    """
    try:
        data = json.loads(request.body)
        action = data.get("action")
        student_ids = data.get("student_ids", [])

        if not action or not student_ids:
            return JsonResponse({"success": False, "error": "Action and student IDs are required"})

        # Validate student IDs
        students = Student.objects.filter(id__in=student_ids, is_active=True)
        if students.count() != len(student_ids):
            return JsonResponse({"success": False, "error": "Some students were not found"})

        results = {"success": 0, "failed": 0, "errors": []}

        with transaction.atomic():
            for student in students:
                try:
                    if action == "reset_status":
                        if student.current_status != "WAITING":
                            student.current_status = "WAITING"
                            student.save(update_fields=["current_status", "status_updated_at"])
                            results["success"] += 1

                    elif action == "mark_inactive":
                        student.is_active = False
                        student.save(update_fields=["is_active"])
                        results["success"] += 1

                    else:
                        results["failed"] += 1
                        results["errors"].append(f"Unknown action: {action}")

                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(f"Failed to update {student.name}: {str(e)}")

        # Log bulk action
        log_audit_event(
            user=request.user,
            action=f"BULK_ACTION_{action.upper()}",
            ip_address=get_client_ip(request),
            details={
                "action": action,
                "student_count": len(student_ids),
                "success_count": results["success"],
                "failed_count": results["failed"],
            },
        )

        # Clear cache
        from .utils import clear_dashboard_cache

        clear_dashboard_cache()

        return JsonResponse(
            {
                "success": True,
                "results": results,
                "message": f"Bulk action completed: {results['success']} successful, {results['failed']} failed",
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid request format"})
    except Exception:
        return JsonResponse({"success": False, "error": "Bulk action failed"})


@login_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="5/m")
@csrf_protect
def reset_all_api(request):
    """
    API endpoint to reset all active students to 'WAITING' status.
    This effectively restarts the dismissal process for all students.
    """
    try:
        data = json.loads(request.body)
        action = data.get("action")

        if action != "reset_all_students":
            return JsonResponse({"success": False, "error": "Invalid action"})

        with transaction.atomic():
            # Get all active students
            students = Student.objects.filter(is_active=True)
            
            if not students.exists():
                return JsonResponse({"success": False, "error": "No active students found"})

            # Reset all students to WAITING status
            reset_count = 0
            for student in students:
                if student.current_status != "WAITING":
                    student.current_status = "WAITING"
                    student.save(update_fields=["current_status", "status_updated_at"])
                    reset_count += 1

            # Log the reset action
            log_audit_event(
                user=request.user,
                action="RESET_ALL_STUDENTS",
                ip_address=get_client_ip(request),
                details={
                    "total_students": students.count(),
                    "students_reset": reset_count,
                    "timestamp": timezone.now().isoformat(),
                },
            )

            # Clear cache to refresh dashboard
            from .utils import clear_dashboard_cache
            clear_dashboard_cache()

            response = JsonResponse(
                {
                    "success": True,
                    "message": f"Successfully reset {reset_count} students to 'Waiting for Parent' status",
                    "total_students": students.count(),
                    "students_reset": reset_count,
                }
            )
            # Prevent caching of reset responses
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            return response

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid request format"})
    except Exception as e:
        return JsonResponse(
            {"success": False, "error": "An error occurred while resetting students"}
        )
