"""
URL configuration for OpenDismissal project.

Main URL routing for the school dismissal management system.
Author: Elena Rodriguez
"""

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path("admin/", admin.site.urls),
    path("dissmissal/", include("dissmissal.urls")),
    path("", lambda request: redirect("dissmissal:dashboard")),  # Redirect root to dashboard
]
