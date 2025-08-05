"""
OpenDismissal URL Configuration

URL patterns for the dismissal management system.
Author: Derek Hayes (Developer 2) & Elena Rodriguez (Developer 1)
"""

from django.urls import path
from . import views, api

app_name = "dissmissal"

urlpatterns = [
    # Main application views
    path("", views.dashboard_view, name="dashboard"),
    path("arrival/", views.parent_arrival_view, name="parent_arrival"),
    path(
        "arrival/<str:code>/",
        views.parent_arrival_view,
        name="parent_arrival_with_code"
    ),
    path("pickup/", views.student_pickup_view, name="student_pickup"),
    path(
        "pickup/<int:student_id>/",
        views.student_pickup_view,
        name="student_pickup_specific"
    ),
    path("students/add/", views.add_student_view, name="add_student"),
    path(
        "students/<int:student_id>/",
        views.student_details_view,
        name="student_details"
    ),
    
    # Mobile interface views
    path("greeter/", views.greeter_mobile_view, name="greeter_mobile"),
    path("releaser/", views.releaser_mobile_view, name="releaser_mobile"),
    # API endpoints for AJAX functionality
    path("api/status/", api.dashboard_status_api, name="dashboard_status_api"),
    path(
        "api/refresh/",
        api.dashboard_refresh_api,
        name="dashboard_refresh_api"
    ),
    path(
        "api/validate-code/",
        api.validate_dismissal_code_api,
        name="validate_code_api"
    ),
    path("api/quick-pickup/", api.quick_pickup_api, name="quick_pickup_api"),
    path("api/search/", api.student_search_api, name="student_search_api"),
    path("api/bulk-action/", api.bulk_action_api, name="bulk_action_api"),
    path("api/reset-all/", api.reset_all_api, name="reset_all_api"),
    
    # Mobile interface API endpoints
    path("api/greeter-submit/", api.greeter_submit_api, name="greeter_submit_api"),
    path("api/releaser-data/", api.releaser_data_api, name="releaser_data_api"),
    path("api/complete-pickup/", api.complete_pickup_api, name="complete_pickup_api"),
]
