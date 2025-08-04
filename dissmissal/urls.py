from django.urls import path
from . import views, api

app_name = "dissmissal"

urlpatterns = [
    # Main application views (will be implemented by Developer 2)
    path("", views.dashboard_view, name="dashboard"),
    path("arrival/", views.parent_arrival_view, name="parent_arrival"),
    path("pickup/<int:student_id>/", views.student_pickup_view, name="student_pickup"),
    path("students/add/", views.add_student_view, name="add_student"),
    # API endpoints for AJAX functionality
    path("api/status/", api.dashboard_status_api, name="dashboard_status_api"),
    path("api/validate-code/", api.validate_dismissal_code_api, name="validate_code_api"),
]
