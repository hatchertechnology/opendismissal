"""
URL configuration for OpenDismissal project.

Main URL routing for the school dismissal management system.
Author: Elena Rodriguez
"""

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.http import HttpResponse
import os


def serve_service_worker(request):
    """Serve the service worker from the project root"""
    sw_path = os.path.join(settings.BASE_DIR, 'sw.js')
    if os.path.exists(sw_path):
        with open(sw_path, 'r') as f:
            content = f.read()
        return HttpResponse(content, content_type='application/javascript')
    else:
        return HttpResponse(
            '// Service worker not found',
            content_type='application/javascript',
            status=404
        )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("dissmissal/", include("dissmissal.urls")),
    path("sw.js", serve_service_worker, name="service_worker"),
    # Redirect root to dashboard
    path("", lambda request: redirect("dissmissal:dashboard")),
]
