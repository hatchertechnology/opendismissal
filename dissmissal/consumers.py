"""
WebSocket consumers for real-time dismissal updates.

Provides multi-browser synchronization for dismissal events using Django Channels.
Author: OpenDismissal Team
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


class DismissalConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time dismissal updates.
    
    Handles WebSocket connections for broadcasting dismissal events to all connected
    staff members. Ensures only authenticated staff can connect and receive updates.
    """

    async def connect(self):
        """Accept WebSocket connection and add to dismissal updates group."""
        # Check if user is authenticated
        if self.scope["user"] is None or isinstance(self.scope["user"], AnonymousUser):
            await self.close(code=4401)  # Custom code for authentication required
            return

        self.group_name = "dismissal_updates"
        
        # Add this connection to the group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Log connection for audit purposes
        logger.info(
            f"WebSocket connected: {self.scope['user'].username} "
            f"from {self.scope.get('client', ['unknown'])[0]}"
        )

    async def disconnect(self, close_code):
        """Remove WebSocket connection from group."""
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        
        # Log disconnection
        if self.scope["user"] and not isinstance(self.scope["user"], AnonymousUser):
            logger.info(
                f"WebSocket disconnected: {self.scope['user'].username} "
                f"with code {close_code}"
            )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages (currently not used)."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            # For now, we don't handle incoming messages from clients
            # This is reserved for future bi-directional features
            logger.warning(
                f"Received unexpected message from {self.scope['user'].username}: "
                f"{message_type}"
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Invalid WebSocket message format: {e}")

    # Group message handlers for different event types
    
    async def student_parent_arrived(self, event):
        """Handle parent arrival broadcast."""
        await self.send(text_data=json.dumps({
            'type': 'parent_arrived',
            'student_id': event['student_id'],
            'student_name': event['student_name'],
            'dismissal_code': event['dismissal_code'],
            'grade': event.get('grade'),
            'teacher': event.get('teacher'),
            'timestamp': event['timestamp'],
            'staff_member': event.get('staff_member'),
        }))

    async def student_picked_up(self, event):
        """Handle student pickup completion broadcast."""
        await self.send(text_data=json.dumps({
            'type': 'pickup_completed',
            'student_id': event['student_id'],
            'student_name': event['student_name'],
            'dismissal_code': event['dismissal_code'],
            'grade': event.get('grade'),
            'teacher': event.get('teacher'),
            'timestamp': event['timestamp'],
            'staff_member': event.get('staff_member'),
        }))

    async def student_status_changed(self, event):
        """Handle general student status change broadcast."""
        await self.send(text_data=json.dumps({
            'type': 'status_changed',
            'student_id': event['student_id'],
            'student_name': event['student_name'],
            'old_status': event.get('old_status'),
            'new_status': event['new_status'],
            'status_display': event.get('status_display'),
            'timestamp': event['timestamp'],
            'staff_member': event.get('staff_member'),
        }))

    async def dismissal_reset(self, event):
        """Handle dismissal reset broadcast."""
        await self.send(text_data=json.dumps({
            'type': 'dismissal_reset',
            'message': event.get('message', 'Dismissal status reset'),
            'timestamp': event['timestamp'],
            'staff_member': event.get('staff_member'),
        }))

    async def bulk_action_completed(self, event):
        """Handle bulk action completion broadcast."""
        await self.send(text_data=json.dumps({
            'type': 'bulk_action',
            'action': event['action'],
            'affected_students': event.get('affected_students', []),
            'success_count': event.get('success_count', 0),
            'failed_count': event.get('failed_count', 0),
            'timestamp': event['timestamp'],
            'staff_member': event.get('staff_member'),
        }))