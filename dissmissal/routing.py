"""
WebSocket URL routing for Django Channels.

Defines URL patterns for WebSocket connections.
Author: OpenDismissal Team
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/dismissal/$', consumers.DismissalConsumer.as_asgi()),
]