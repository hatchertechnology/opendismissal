from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.utils import timezone
from .models import Student


@login_required
@require_http_methods(["GET"])
def dashboard_status_api(request):
    """
    Lightweight JSON endpoint for AJAX polling dashboard updates.
    Provides cached data for performance.
    """
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
                    "last_updated": student.status_updated_at.isoformat()
                    if student.status_updated_at
                    else None,
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

        # Dashboard statistics
        waiting_count = students.filter(current_status="WAITING").count()
        arrived_count = students.filter(current_status="PARENT_ARRIVED").count()
        picked_up_count = students.filter(current_status="PICKED_UP").count()

        data = {
            "students": student_data,
            "stats": {
                "total": len(student_data),
                "waiting": waiting_count,
                "parent_arrived": arrived_count,
                "picked_up": picked_up_count,
                "last_updated": timezone.now().isoformat(),
            },
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
    dismissal_code = request.POST.get("code", "").upper().strip()

    if not dismissal_code:
        return JsonResponse({"valid": False, "error": "No code provided"})

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
