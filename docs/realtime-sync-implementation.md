# Real-Time Multi-Browser Sync Implementation

This document describes the implementation of atomic real-time multi-browser synchronization for OpenDismissal using Django Channels and WebSockets.

## Overview

The implementation provides instant synchronization across all browser windows when dismissal events occur, ensuring that staff members see updates in real-time without needing to refresh their browsers. All database operations are atomic and WebSocket broadcasts only occur after successful database commits.

## Architecture

### Components Added

1. **Django Channels Integration**
   - Added `channels` and `channels-redis` dependencies
   - Configured Redis-backed channel layer for message passing
   - Updated ASGI configuration to handle WebSocket connections

2. **WebSocket Consumer** (`dissmissal/consumers.py`)
   - `DismissalConsumer` handles WebSocket connections
   - Authenticates users before accepting connections
   - Processes and broadcasts different event types

3. **Broadcasting Utilities** (`dissmissal/utils.py`)
   - Functions to broadcast events to all connected clients
   - Error handling for Redis connection failures
   - Graceful degradation when WebSockets are unavailable

4. **API Enhancements** (`dissmissal/api.py`)
   - Modified existing endpoints to use `transaction.on_commit()`
   - Ensures broadcasts only occur after successful database commits
   - Maintains atomic operation guarantees

## Event Types

The system broadcasts these real-time events:

- **Parent Arrived**: When a parent checks in using their dismissal code
- **Pickup Completed**: When a student is released to their parent  
- **Status Changed**: When a student's status is manually updated
- **Dismissal Reset**: When all students are reset to "Waiting" status
- **Bulk Action**: When bulk operations are performed on multiple students

## WebSocket Message Format

Messages sent to browsers follow this structure:

```json
{
  "type": "parent_arrived",
  "student_id": 123,
  "student_name": "John Doe",
  "dismissal_code": "ABC123", 
  "grade": "5th",
  "teacher": "Ms. Smith",
  "timestamp": "2024-01-15T14:30:00Z",
  "staff_member": "Jane Admin"
}
```

## Configuration

### Settings Added to `settings.py`:

```python
INSTALLED_APPS = [
    "daphne",  # ASGI server
    "channels", # Django Channels
    # ... existing apps
]

ASGI_APPLICATION = "opendiss.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
            "capacity": 1500,
            "expiry": 60,
        },
    },
}
```

### ASGI Configuration (`opendiss/asgi.py`):

```python
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from dissmissal.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
```

## API Endpoint Changes

Modified these endpoints to include real-time broadcasting:

- `greeter_submit_api` - Broadcasts parent arrival events
- `complete_pickup_api` - Broadcasts pickup completion  
- `quick_pickup_api` - Broadcasts pickup completion
- `reset_all_api` - Broadcasts dismissal reset events

Example implementation pattern:

```python
@transaction.atomic
def greeter_submit_api(request):
    # ... database operations ...
    
    # Broadcast after successful commit
    def notify_parent_arrival():
        broadcast_parent_arrival(student, request.user)
    
    transaction.on_commit(notify_parent_arrival)
```

## Frontend Integration

### WebSocket Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/dismissal/');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
        case 'parent_arrived':
            updateStudentStatus(data.student_id, 'PARENT_ARRIVED');
            showNotification(`${data.student_name} parent arrived`);
            break;
        case 'pickup_completed':
            updateStudentStatus(data.student_id, 'PICKED_UP');
            showNotification(`${data.student_name} pickup complete`);
            break;
        // ... handle other event types
    }
};
```

## Testing

### Test Coverage Added

- **WebSocket Connection Tests**: Authentication and connection handling
- **Broadcast Function Tests**: Message format and error handling  
- **Integration Tests**: API endpoint broadcasting with `transaction.on_commit()`
- **Atomic Operation Tests**: Database rollback prevention of broadcasts

### Running Tests

```bash
# Run real-time sync tests
uv run python manage.py test dissmissal.tests.test_realtime

# Run all tests  
uv run python manage.py test dissmissal.tests
```

## Deployment Requirements

### Production Setup

1. **Redis Instance**: Required for channel layer message passing
2. **ASGI Server**: Use Daphne (included) or uvicorn for WebSocket support
3. **Environment Variables**: 
   - `REDIS_URL`: Redis connection string
   - `ASGI_APPLICATION`: Set to "opendiss.asgi.application"

### Docker Configuration

The existing `docker-compose.yml` already includes Redis. To enable WebSockets:

```yaml
web:
  command: >
    sh -c "uv run python manage.py migrate &&
           uv run python manage.py collectstatic --noinput &&
           uv run daphne -b 0.0.0.0 -p 8000 opendiss.asgi:application"
```

### Kubernetes Deployment

For K8s deployment, ensure:
- Redis service is available and accessible
- WebSocket traffic is properly routed through ingress
- Load balancer supports sticky sessions or use Redis for session storage

## Error Handling

### Graceful Degradation

The system handles these failure scenarios gracefully:

- **Redis Unavailable**: Broadcasting fails silently, API operations continue
- **WebSocket Disconnection**: Clients attempt automatic reconnection
- **Channel Layer Errors**: Logged as warnings, don't affect API responses

### Monitoring

Monitor these metrics in production:
- WebSocket connection count
- Redis connection health
- Broadcasting success/failure rates
- Message queue length

## Security Considerations

- **Authentication Required**: Only authenticated staff can connect to WebSockets
- **Same-Origin Policy**: WebSocket connections validated against ALLOWED_HOSTS
- **Message Validation**: All broadcast data is sanitized and validated
- **Rate Limiting**: Existing API rate limits apply to triggering events

## Performance

### Scalability

- **Horizontal Scaling**: Multiple Django instances can share Redis channel layer
- **Message Queuing**: Redis handles message persistence and delivery
- **Connection Limits**: Configure based on expected concurrent staff users

### Optimization

- **Message Expiry**: Set to 60 seconds to prevent memory buildup
- **Connection Pooling**: Redis connections are pooled automatically
- **Selective Broadcasting**: Only sends relevant data to reduce bandwidth

## Demo

A complete working demo is included in `realtime_demo.html` that shows:
- WebSocket connection establishment
- Real-time event display
- Multi-browser synchronization testing
- Error handling and reconnection

Open multiple browser windows to this page and trigger dismissal events through the API to see instant synchronization.

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failed**: 
   - Check Redis is running and accessible
   - Verify REDIS_URL configuration
   - Ensure ASGI_APPLICATION setting is correct

2. **Events Not Broadcasting**:
   - Check Redis connection in logs
   - Verify transaction.on_commit() callbacks are executing
   - Confirm WebSocket consumer is receiving messages

3. **High Memory Usage**:
   - Check Redis memory usage
   - Verify message expiry settings
   - Monitor connection count

### Debug Commands

```bash
# Check Redis connection
redis-cli ping

# Test WebSocket endpoint
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: test" \
  http://localhost:8000/ws/dismissal/

# View Django logs
tail -f logs/dissmissal_audit.log
```

This implementation provides robust, scalable real-time synchronization that enhances the OpenDismissal system's usability and coordination capabilities.