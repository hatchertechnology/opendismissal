# Developer 3: Frontend & Templates

**Developer:** Frontend & UX Lead  
**Branch:** `feature/frontend-templates`  
**Timeline:** Days 2-12 of development  
**Dependencies:** Developer 1's models/APIs, Developer 2's views/forms

## Project Context

You're creating the user interface for OpenDismissal - a mobile-first web application used by school staff during outdoor dismissal periods. Staff will use smartphones and tablets in bright sunlight while coordinating student pickups, so usability and readability are critical.

**Your role:** Transform the backend functionality into an intuitive, responsive interface that enables efficient dismissal coordination on mobile devices while maintaining professional appearance on desktop computers.

## Design Requirements & Constraints

### Mobile-First Considerations
- **Primary use case:** iPhone/Android smartphones held by staff outdoors
- **Bright sunlight readability:** High contrast colors, large text
- **Touch targets:** Minimum 44px for iOS accessibility guidelines
- **Input prevention:** Avoid zoom-in on iOS when focusing inputs
- **Network conditions:** Minimize data usage, cache aggressively

### User Experience Goals
- **Speed:** Critical actions completed in <3 taps
- **Clarity:** Status immediately visible at a glance  
- **Error prevention:** Clear validation with helpful messages
- **Accessibility:** Works with screen readers and high contrast modes

## Technical Integration Points

### Data from Developer 2's Views

Your templates will receive these context variables:

```python
# Dashboard context
{
    'page_obj': paginated_students,
    'students': list_of_student_objects,
    'stats': {
        'total_active': 25,
        'waiting': 15,
        'parent_arrived': 8,
        'picked_up': 2,
        'waiting_percent': 60.0,
        'arrived_percent': 32.0, 
        'picked_up_percent': 8.0
    },
    'grades': ['1st', '2nd', '3rd', '4th', '5th'],
    'teachers': ['Mrs. Smith', 'Mr. Davis', 'Ms. Garcia'],
    'current_filters': {
        'status': 'all',
        'grade': 'all', 
        'search': ''
    },
    'last_updated': datetime_object,
    'page_title': 'Dismissal Dashboard'
}

# Form contexts (parent arrival, student pickup, add student)
{
    'form': form_object,  # Django form with Bootstrap-ready widgets
    'recent_arrivals': list_of_pickup_events,
    'ready_students': list_of_students_ready_for_pickup,
    'page_title': 'Log Parent Arrival'
}
```

### APIs from Developer 1

Your JavaScript will call these endpoints:

```javascript
// Dashboard status updates
GET /dissmissal/api/status/
GET /dissmissal/api/refresh/?last_update=2025-08-04T15:30:00Z

// Form validation  
POST /dissmissal/api/validate-code/
POST /dissmissal/api/quick-pickup/
```

## Template Structure Implementation

### Base Template Architecture

Create `dissmissal/templates/dissmissal/base.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <meta name="format-detection" content="telephone=no">
    <meta name="theme-color" content="#0d6efd">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    
    <title>{% block title %}OpenDismissal{% endblock %} - {{ page_title|default:"School Dismissal System" }}</title>
    
    <!-- Bootstrap 5.3 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <!-- Bootstrap Icons -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
    
    <!-- Custom CSS -->
    <link rel="stylesheet" href="{% load static %}{% static 'dissmissal/css/main.css' %}">
    
    {% block extra_css %}{% endblock %}
    
    <style>
        /* Critical above-fold CSS inlined for performance */
        
        /* iOS-specific fixes to prevent zoom on input focus */
        input[type="text"], 
        input[type="email"], 
        input[type="password"], 
        input[type="number"], 
        input[type="tel"], 
        textarea, 
        select {
            font-size: 16px !important; /* Prevents iOS zoom */
        }
        
        /* Mobile-optimized touch targets */
        .btn-mobile {
            min-height: 44px;
            min-width: 44px;
            font-size: 16px;
            padding: 12px 20px;
            font-weight: 500;
        }
        
        .form-control-mobile {
            font-size: 16px;
            padding: 12px 16px;
            min-height: 44px;
            border-radius: 8px;
        }
        
        /* High contrast for outdoor visibility */
        .status-waiting { 
            background-color: #fff3cd; 
            border-color: #ffecb5; 
            color: #664d03; 
        }
        .status-arrived { 
            background-color: #d1ecf1; 
            border-color: #bee5eb; 
            color: #0c5460; 
        }
        .status-picked-up { 
            background-color: #d4edda; 
            border-color: #c3e6cb; 
            color: #155724; 
        }
        
        /* Loading states */
        .loading {
            opacity: 0.6;
            pointer-events: none;
        }
        
        /* Accessibility improvements */
        .visually-hidden-focusable:not(:focus):not(:focus-within) {
            position: absolute !important;
            width: 1px !important;
            height: 1px !important;
            padding: 0 !important;
            margin: -1px !important;
            overflow: hidden !important;
            clip: rect(0, 0, 0, 0) !important;
            white-space: nowrap !important;
            border: 0 !important;
        }
    </style>
</head>
<body>
    <!-- Skip navigation for accessibility -->
    <a href="#main-content" class="visually-hidden-focusable btn btn-primary">Skip to main content</a>
    
    <!-- Navigation Header -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary sticky-top">
        <div class="container-fluid">
            <!-- Logo/Brand -->
            <a class="navbar-brand fw-bold" href="{% url 'dissmissal:dashboard' %}">
                <i class="bi bi-mortarboard-fill me-2"></i>
                OpenDismissal
            </a>
            
            <!-- Mobile menu toggle -->
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            
            <!-- Navigation items -->
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link {% if request.resolver_match.url_name == 'dashboard' %}active{% endif %}" 
                           href="{% url 'dissmissal:dashboard' %}">
                            <i class="bi bi-speedometer2 me-1"></i>
                            Dashboard
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link {% if request.resolver_match.url_name == 'parent_arrival' %}active{% endif %}" 
                           href="{% url 'dissmissal:parent_arrival' %}">
                            <i class="bi bi-person-plus me-1"></i>
                            Parent Arrival
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link {% if request.resolver_match.url_name == 'student_pickup' %}active{% endif %}" 
                           href="{% url 'dissmissal:student_pickup' %}">
                            <i class="bi bi-check-circle me-1"></i>
                            Complete Pickup
                        </a>
                    </li>
                </ul>
                
                <!-- User info and logout -->
                <div class="navbar-nav">
                    <span class="navbar-text me-3">
                        <i class="bi bi-person-circle me-1"></i>
                        {{ user.get_full_name|default:user.username }}
                    </span>
                    <a class="nav-link" href="{% url 'admin:logout' %}">
                        <i class="bi bi-box-arrow-right me-1"></i>
                        Logout
                    </a>
                </div>
            </div>
        </div>
    </nav>
    
    <!-- Main content area -->
    <main id="main-content" class="container-fluid py-3">
        <!-- Alert messages -->
        {% if messages %}
            <div id="messages-container">
                {% for message in messages %}
                    <div class="alert alert-{{ message.tags|default:'info' }} alert-dismissible fade show" role="alert">
                        <i class="bi bi-{% if message.tags == 'error' %}exclamation-triangle{% elif message.tags == 'warning' %}exclamation-circle{% elif message.tags == 'success' %}check-circle{% else %}info-circle{% endif %} me-2"></i>
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>
                {% endfor %}
            </div>
        {% endif %}
        
        <!-- Page header -->
        {% block page_header %}
            {% if page_title %}
                <div class="row mb-3">
                    <div class="col">
                        <h1 class="h2 mb-0">{{ page_title }}</h1>
                        {% block page_subtitle %}{% endblock %}
                    </div>
                    {% block page_actions %}{% endblock %}
                </div>
            {% endif %}
        {% endblock %}
        
        <!-- Page content -->
        {% block content %}{% endblock %}
    </main>
    
    <!-- Footer -->
    <footer class="bg-light border-top py-3 mt-auto">
        <div class="container-fluid">
            <div class="row align-items-center">
                <div class="col-md-6">
                    <small class="text-muted">
                        OpenDismissal - Secure Student Dismissal Management
                    </small>
                </div>
                <div class="col-md-6 text-md-end">
                    <small class="text-muted">
                        Last updated: <span id="last-update-time">{{ last_updated|date:"g:i A" }}</span>
                    </small>
                </div>
            </div>
        </div>
    </footer>
    
    <!-- JavaScript -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{% load static %}{% static 'dissmissal/js/main.js' %}"></script>
    
    {% block extra_js %}{% endblock %}
    
    <!-- Global error handling -->
    <script>
        // Global error handler for AJAX requests
        window.addEventListener('error', function(e) {
            console.error('Global error:', e.error);
            // Could send to error tracking service
        });
        
        // Handle network failures gracefully
        window.addEventListener('offline', function() {
            showMessage('You are offline. Some features may be limited.', 'warning');
        });
        
        window.addEventListener('online', function() {
            showMessage('Connection restored.', 'success');
            // Refresh data when back online
            if (typeof refreshDashboard === 'function') {
                refreshDashboard();
            }
        });
    </script>
</body>
</html>
```

### Dashboard Template

Create `dissmissal/templates/dissmissal/dashboard.html`:

```html
{% extends 'dissmissal/base.html' %}
{% load static %}

{% block title %}Dashboard{% endblock %}

{% block page_header %}
    <div class="row mb-4">
        <div class="col">
            <h1 class="h2 mb-2">
                <i class="bi bi-speedometer2 me-2"></i>
                Dismissal Dashboard
            </h1>
            <p class="text-muted mb-0">
                Real-time view of student dismissal status
            </p>
        </div>
        <div class="col-auto">
            <div class="btn-group" role="group">
                <a href="{% url 'dissmissal:parent_arrival' %}" class="btn btn-primary btn-mobile">
                    <i class="bi bi-person-plus me-1"></i>
                    Log Arrival
                </a>
                <a href="{% url 'dissmissal:student_pickup' %}" class="btn btn-success btn-mobile">
                    <i class="bi bi-check-circle me-1"></i>
                    Complete Pickup
                </a>
            </div>
        </div>
    </div>
{% endblock %}

{% block content %}
    <!-- Statistics Cards -->
    <div class="row mb-4" id="stats-cards">
        <div class="col-6 col-lg-3 mb-3">
            <div class="card bg-primary text-white">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <div class="fs-4 fw-bold" id="total-count">{{ stats.total_active }}</div>
                            <div class="small">Total Active</div>
                        </div>
                        <i class="bi bi-people fs-1 opacity-75"></i>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-6 col-lg-3 mb-3">
            <div class="card bg-warning text-dark">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <div class="fs-4 fw-bold" id="waiting-count">{{ stats.waiting }}</div>
                            <div class="small">Waiting</div>
                        </div>
                        <i class="bi bi-clock fs-1 opacity-75"></i>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-6 col-lg-3 mb-3">
            <div class="card bg-info text-white">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <div class="fs-4 fw-bold" id="arrived-count">{{ stats.parent_arrived }}</div>
                            <div class="small">Parent Arrived</div>
                        </div>
                        <i class="bi bi-person-check fs-1 opacity-75"></i>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-6 col-lg-3 mb-3">
            <div class="card bg-success text-white">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <div class="fs-4 fw-bold" id="picked-up-count">{{ stats.picked_up }}</div>
                            <div class="small">Picked Up</div>
                        </div>
                        <i class="bi bi-check-circle fs-1 opacity-75"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Filters and Search -->
    <div class="card mb-4">
        <div class="card-body">
            <form method="GET" class="row g-3" id="filter-form">
                <div class="col-md-3">
                    <label for="status-filter" class="form-label">Status Filter</label>
                    <select name="status" id="status-filter" class="form-select">
                        <option value="all" {% if current_filters.status == 'all' %}selected{% endif %}>All Students</option>
                        <option value="WAITING" {% if current_filters.status == 'WAITING' %}selected{% endif %}>Waiting for Parent</option>
                        <option value="PARENT_ARRIVED" {% if current_filters.status == 'PARENT_ARRIVED' %}selected{% endif %}>Parent Has Arrived</option>
                        <option value="PICKED_UP" {% if current_filters.status == 'PICKED_UP' %}selected{% endif %}>Picked Up</option>
                    </select>
                </div>
                
                <div class="col-md-3">
                    <label for="grade-filter" class="form-label">Grade Filter</label>
                    <select name="grade" id="grade-filter" class="form-select">
                        <option value="all" {% if current_filters.grade == 'all' %}selected{% endif %}>All Grades</option>
                        {% for grade in grades %}
                            <option value="{{ grade }}" {% if current_filters.grade == grade %}selected{% endif %}>{{ grade }}</option>
                        {% endfor %}
                    </select>
                </div>
                
                <div class="col-md-4">
                    <label for="search-input" class="form-label">Search</label>
                    <input type="text" name="search" id="search-input" class="form-control" 
                           placeholder="Name, code, or teacher..." value="{{ current_filters.search }}">
                </div>
                
                <div class="col-md-2">
                    <label class="form-label">&nbsp;</label>
                    <div class="d-grid">
                        <button type="submit" class="btn btn-outline-primary">
                            <i class="bi bi-search me-1"></i>
                            Filter
                        </button>
                    </div>
                </div>
            </form>
        </div>
    </div>
    
    <!-- Student List -->
    <div class="card">
        <div class="card-header d-flex justify-content-between align-items-center">
            <h5 class="mb-0">
                <i class="bi bi-list-ul me-2"></i>
                Student Status
            </h5>
            <div class="d-flex align-items-center">
                <button id="refresh-btn" class="btn btn-sm btn-outline-secondary me-2" onclick="refreshDashboard()">
                    <i class="bi bi-arrow-clockwise me-1"></i>
                    Refresh
                </button>
                <small class="text-muted">
                    Auto-refresh: <span id="refresh-countdown">30</span>s
                </small>
            </div>
        </div>
        
        <div class="card-body p-0">
            {% if students %}
                <div class="table-responsive">
                    <table class="table table-hover mb-0" id="students-table">
                        <thead class="table-light">
                            <tr>
                                <th scope="col">Student</th>
                                <th scope="col" class="d-none d-md-table-cell">Grade</th>
                                <th scope="col" class="d-none d-lg-table-cell">Teacher</th>
                                <th scope="col">Status</th>
                                <th scope="col">Code</th>
                                <th scope="col">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for student in students %}
                                <tr data-student-id="{{ student.id }}" 
                                    class="{% if student.current_status == 'PARENT_ARRIVED' %}table-warning{% elif student.current_status == 'PICKED_UP' %}table-success{% endif %}">
                                    <td>
                                        <div class="fw-medium">{{ student.name }}</div>
                                        <div class="small text-muted d-md-none">
                                            {{ student.grade }} - {{ student.teacher }}
                                        </div>
                                    </td>
                                    <td class="d-none d-md-table-cell">{{ student.grade }}</td>
                                    <td class="d-none d-lg-table-cell">{{ student.teacher }}</td>
                                    <td>
                                        <span class="badge bg-{% if student.current_status == 'WAITING' %}warning{% elif student.current_status == 'PARENT_ARRIVED' %}info{% else %}success{% endif %}">
                                            {% if student.current_status == 'WAITING' %}
                                                <i class="bi bi-clock me-1"></i>Waiting
                                            {% elif student.current_status == 'PARENT_ARRIVED' %}
                                                <i class="bi bi-person-check me-1"></i>Parent Here
                                            {% else %}
                                                <i class="bi bi-check-circle me-1"></i>Picked Up
                                            {% endif %}
                                        </span>
                                    </td>
                                    <td>
                                        <code class="user-select-all">{{ student.dismissal_code }}</code>
                                    </td>
                                    <td>
                                        <div class="btn-group-sm" role="group">
                                            {% if student.current_status == 'PARENT_ARRIVED' %}
                                                <button class="btn btn-success btn-sm quick-pickup-btn" 
                                                        data-student-id="{{ student.id }}"
                                                        data-student-name="{{ student.name }}">
                                                    <i class="bi bi-check-circle me-1"></i>
                                                    <span class="d-none d-sm-inline">Complete</span>
                                                </button>
                                            {% elif student.current_status == 'WAITING' %}
                                                <a href="{% url 'dissmissal:parent_arrival' %}" 
                                                   class="btn btn-primary btn-sm">
                                                    <i class="bi bi-person-plus me-1"></i>
                                                    <span class="d-none d-sm-inline">Log Arrival</span>
                                                </a>
                                            {% else %}
                                                <span class="text-success small">
                                                    <i class="bi bi-check-circle me-1"></i>
                                                    Complete
                                                </span>
                                            {% endif %}
                                        </div>
                                    </td>
                                </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                
                <!-- Pagination -->
                {% if page_obj.has_other_pages %}
                    <div class="card-footer">
                        <nav aria-label="Student list pagination">
                            <ul class="pagination pagination-sm justify-content-center mb-0">
                                {% if page_obj.has_previous %}
                                    <li class="page-item">
                                        <a class="page-link" href="?page=1{% if current_filters.status != 'all' %}&status={{ current_filters.status }}{% endif %}{% if current_filters.grade != 'all' %}&grade={{ current_filters.grade }}{% endif %}{% if current_filters.search %}&search={{ current_filters.search }}{% endif %}">
                                            <i class="bi bi-chevron-double-left"></i>
                                        </a>
                                    </li>
                                    <li class="page-item">
                                        <a class="page-link" href="?page={{ page_obj.previous_page_number }}{% if current_filters.status != 'all' %}&status={{ current_filters.status }}{% endif %}{% if current_filters.grade != 'all' %}&grade={{ current_filters.grade }}{% endif %}{% if current_filters.search %}&search={{ current_filters.search }}{% endif %}">
                                            <i class="bi bi-chevron-left"></i>
                                        </a>
                                    </li>
                                {% endif %}
                                
                                <li class="page-item active">
                                    <span class="page-link">
                                        Page {{ page_obj.number }} of {{ page_obj.paginator.num_pages }}
                                    </span>
                                </li>
                                
                                {% if page_obj.has_next %}
                                    <li class="page-item">
                                        <a class="page-link" href="?page={{ page_obj.next_page_number }}{% if current_filters.status != 'all' %}&status={{ current_filters.status }}{% endif %}{% if current_filters.grade != 'all' %}&grade={{ current_filters.grade }}{% endif %}{% if current_filters.search %}&search={{ current_filters.search }}{% endif %}">
                                            <i class="bi bi-chevron-right"></i>
                                        </a>
                                    </li>
                                    <li class="page-item">
                                        <a class="page-link" href="?page={{ page_obj.paginator.num_pages }}{% if current_filters.status != 'all' %}&status={{ current_filters.status }}{% endif %}{% if current_filters.grade != 'all' %}&grade={{ current_filters.grade }}{% endif %}{% if current_filters.search %}&search={{ current_filters.search }}{% endif %}">
                                            <i class="bi bi-chevron-double-right"></i>
                                        </a>
                                    </li>
                                {% endif %}
                            </ul>
                        </nav>
                    </div>
                {% endif %}
            {% else %}
                <div class="text-center py-5">
                    <i class="bi bi-inbox display-1 text-muted"></i>
                    <h4 class="mt-3">No Students Found</h4>
                    <p class="text-muted">
                        {% if current_filters.search or current_filters.status != 'all' or current_filters.grade != 'all' %}
                            Try adjusting your filters or search terms.
                        {% else %}
                            No active students in the system. Add students through the admin panel.
                        {% endif %}
                    </p>
                    {% if current_filters.search or current_filters.status != 'all' or current_filters.grade != 'all' %}
                        <a href="{% url 'dissmissal:dashboard' %}" class="btn btn-outline-primary">
                            <i class="bi bi-arrow-counterclockwise me-1"></i>
                            Clear Filters
                        </a>
                    {% endif %}
                </div>
            {% endif %}
        </div>
    </div>
    
    <!-- Quick Pickup Modal -->
    <div class="modal fade" id="quickPickupModal" tabindex="-1" aria-labelledby="quickPickupModalLabel" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="quickPickupModalLabel">Complete Pickup</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <p>Complete pickup for <strong id="pickup-student-name"></strong>?</p>
                    <div class="mb-3">
                        <label for="pickup-notes" class="form-label">Notes (optional)</label>
                        <textarea id="pickup-notes" class="form-control" rows="3" 
                                  placeholder="Optional notes about the pickup..."></textarea>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-success" id="confirm-pickup-btn">
                        <i class="bi bi-check-circle me-1"></i>
                        Complete Pickup
                    </button>
                </div>
            </div>
        </div>
    </div>
{% endblock %}

{% block extra_js %}
    <script>
        // Dashboard-specific JavaScript
        let refreshTimer;
        let countdownTimer;
        let countdownSeconds = 30;
        
        // Auto-refresh functionality
        function startRefreshCountdown() {
            countdownSeconds = 30;
            countdownTimer = setInterval(function() {
                countdownSeconds--;
                document.getElementById('refresh-countdown').textContent = countdownSeconds;
                
                if (countdownSeconds <= 0) {
                    refreshDashboard();
                }
            }, 1000);
        }
        
        function refreshDashboard() {
            clearInterval(countdownTimer);
            
            const refreshBtn = document.getElementById('refresh-btn');
            const icon = refreshBtn.querySelector('i');
            
            // Show loading state
            icon.className = 'bi bi-arrow-clockwise spin me-1';
            refreshBtn.disabled = true;
            
            fetch('/dissmissal/api/refresh/', {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.updated) {
                    updateDashboardData(data);
                }
                
                // Reset refresh button
                icon.className = 'bi bi-arrow-clockwise me-1';
                refreshBtn.disabled = false;
                
                // Update last updated time
                const now = new Date();
                document.getElementById('last-update-time').textContent = 
                    now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
                
                startRefreshCountdown();
            })
            .catch(error => {
                console.error('Refresh failed:', error);
                showMessage('Failed to refresh dashboard data', 'error');
                
                // Reset refresh button
                icon.className = 'bi bi-arrow-clockwise me-1';
                refreshBtn.disabled = false;
                startRefreshCountdown();
            });
        }
        
        function updateDashboardData(data) {
            // Update statistics cards
            if (data.stats) {
                document.getElementById('total-count').textContent = data.stats.total_active;
                document.getElementById('waiting-count').textContent = data.stats.waiting;
                document.getElementById('arrived-count').textContent = data.stats.parent_arrived;
                document.getElementById('picked-up-count').textContent = data.stats.picked_up;
            }
            
            // Update student table if needed
            if (data.students) {
                updateStudentTable(data.students);
            }
        }
        
        function updateStudentTable(students) {
            const tbody = document.querySelector('#students-table tbody');
            if (!tbody) return;
            
            // This is a simplified update - in practice you might want to 
            // be more surgical about which rows to update
            students.forEach(student => {
                const row = document.querySelector(`tr[data-student-id="${student.id}"]`);
                if (row) {
                    // Update status badge
                    const statusCell = row.querySelector('td:nth-child(4) .badge');
                    if (statusCell) {
                        updateStatusBadge(statusCell, student.current_status);
                    }
                    
                    // Update actions
                    const actionsCell = row.querySelector('td:last-child');
                    if (actionsCell) {
                        updateActionButtons(actionsCell, student);
                    }
                    
                    // Update row highlighting
                    row.className = '';
                    if (student.current_status === 'PARENT_ARRIVED') {
                        row.classList.add('table-warning');
                    } else if (student.current_status === 'PICKED_UP') {
                        row.classList.add('table-success');
                    }
                }
            });
        }
        
        function updateStatusBadge(badgeElement, status) {
            badgeElement.className = 'badge bg-' + 
                (status === 'WAITING' ? 'warning' : 
                 status === 'PARENT_ARRIVED' ? 'info' : 'success');
            
            badgeElement.innerHTML = 
                status === 'WAITING' ? '<i class="bi bi-clock me-1"></i>Waiting' :
                status === 'PARENT_ARRIVED' ? '<i class="bi bi-person-check me-1"></i>Parent Here' :
                '<i class="bi bi-check-circle me-1"></i>Picked Up';
        }
        
        // Quick pickup functionality
        let currentPickupStudentId = null;
        
        document.addEventListener('DOMContentLoaded', function() {
            // Initialize refresh countdown
            startRefreshCountdown();
            
            // Setup quick pickup modal
            const quickPickupModal = new bootstrap.Modal(document.getElementById('quickPickupModal'));
            
            // Handle quick pickup button clicks
            document.addEventListener('click', function(e) {
                if (e.target.closest('.quick-pickup-btn')) {
                    const btn = e.target.closest('.quick-pickup-btn');
                    currentPickupStudentId = btn.dataset.studentId;
                    const studentName = btn.dataset.studentName;
                    
                    document.getElementById('pickup-student-name').textContent = studentName;
                    document.getElementById('pickup-notes').value = '';
                    
                    quickPickupModal.show();
                }
            });
            
            // Handle pickup confirmation
            document.getElementById('confirm-pickup-btn').addEventListener('click', function() {
                if (currentPickupStudentId) {
                    completeQuickPickup(currentPickupStudentId);
                }
            });
        });
        
        function completeQuickPickup(studentId) {
            const notes = document.getElementById('pickup-notes').value;
            const confirmBtn = document.getElementById('confirm-pickup-btn');
            
            // Show loading state
            confirmBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
            confirmBtn.disabled = true;
            
            fetch('/dissmissal/api/quick-pickup/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: `student_id=${studentId}&notes=${encodeURIComponent(notes)}`
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage(data.message, 'success');
                    
                    // Close modal
                    bootstrap.Modal.getInstance(document.getElementById('quickPickupModal')).hide();
                    
                    // Refresh dashboard data
                    setTimeout(refreshDashboard, 500);
                } else {
                    showMessage(data.error, 'error');
                }
            })
            .catch(error => {
                console.error('Quick pickup failed:', error);
                showMessage('Failed to complete pickup. Please try again.', 'error');
            })
            .finally(() => {
                // Reset button
                confirmBtn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Complete Pickup';
                confirmBtn.disabled = false;
            });
        }
        
        // Filter form auto-submit on mobile
        document.getElementById('status-filter').addEventListener('change', function() {
            if (window.innerWidth < 768) {
                document.getElementById('filter-form').submit();
            }
        });
        
        document.getElementById('grade-filter').addEventListener('change', function() {
            if (window.innerWidth < 768) {
                document.getElementById('filter-form').submit();
            }
        });
    </script>
{% endblock %}
```

### Form Templates

Create `dissmissal/templates/dissmissal/parent_arrival.html`:

```html
{% extends 'dissmissal/base.html' %}
{% load static %}

{% block title %}Parent Arrival{% endblock %}

{% block page_actions %}
    <div class="col-auto">
        <a href="{% url 'dissmissal:dashboard' %}" class="btn btn-outline-secondary">
            <i class="bi bi-arrow-left me-1"></i>
            Back to Dashboard
        </a>
    </div>
{% endblock %}

{% block content %}
    <div class="row">
        <div class="col-lg-8">
            <!-- Parent Arrival Form -->
            <div class="card">
                <div class="card-header">
                    <h5 class="mb-0">
                        <i class="bi bi-person-plus me-2"></i>
                        Log Parent Arrival
                    </h5>
                </div>
                <div class="card-body">
                    <form method="post" id="parent-arrival-form">
                        {% csrf_token %}
                        
                        <div class="mb-4">
                            <label for="{{ form.dismissal_code.id_for_label }}" class="form-label fs-5">
                                <i class="bi bi-key me-2"></i>
                                Dismissal Code
                            </label>
                            {{ form.dismissal_code }}
                            {% if form.dismissal_code.help_text %}
                                <div class="form-text">{{ form.dismissal_code.help_text }}</div>
                            {% endif %}
                            {% if form.dismissal_code.errors %}
                                <div class="invalid-feedback d-block">
                                    {% for error in form.dismissal_code.errors %}
                                        {{ error }}
                                    {% endfor %}
                                </div>
                            {% endif %}
                            
                            <!-- Real-time validation feedback -->
                            <div id="code-validation-feedback" class="mt-2"></div>
                        </div>
                        
                        <div class="mb-4">
                            <label for="{{ form.notes.id_for_label }}" class="form-label">
                                <i class="bi bi-chat-text me-2"></i>
                                Notes (Optional)
                            </label>
                            {{ form.notes }}
                            {% if form.notes.help_text %}
                                <div class="form-text">{{ form.notes.help_text }}</div>
                            {% endif %}
                        </div>
                        
                        <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                            <button type="submit" class="btn btn-primary btn-lg btn-mobile" id="submit-btn">
                                <i class="bi bi-person-check me-2"></i>
                                Log Parent Arrival
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
        
        <div class="col-lg-4">
            <!-- Recent Arrivals -->
            {% if recent_arrivals %}
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0">
                            <i class="bi bi-clock-history me-2"></i>
                            Recent Arrivals
                        </h6>
                    </div>
                    <div class="card-body p-0">
                        <div class="list-group list-group-flush">
                            {% for event in recent_arrivals %}
                                <div class="list-group-item">
                                    <div class="d-flex justify-content-between align-items-start">
                                        <div class="flex-grow-1">
                                            <h6 class="mb-1">{{ event.student.name }}</h6>
                                            <p class="mb-1 small text-muted">
                                                {{ event.student.grade }} - {{ event.student.teacher }}
                                            </p>
                                            <small class="text-muted">
                                                <i class="bi bi-person me-1"></i>
                                                {{ event.staff_member.get_full_name|default:event.staff_member.username }}
                                            </small>
                                        </div>
                                        <small class="text-muted">
                                            {{ event.timestamp|timesince }} ago
                                        </small>
                                    </div>
                                </div>
                            {% endfor %}
                        </div>
                    </div>
                </div>
            {% endif %}
            
            <!-- Help Information -->
            <div class="card mt-3">
                <div class="card-header">
                    <h6 class="mb-0">
                        <i class="bi bi-info-circle me-2"></i>
                        Instructions
                    </h6>
                </div>
                <div class="card-body">
                    <ol class="mb-0">
                        <li class="mb-2">Ask the parent for their dismissal code</li>
                        <li class="mb-2">Enter the code in the field above</li>
                        <li class="mb-2">The system will validate the code automatically</li>
                        <li class="mb-0">Click "Log Parent Arrival" to confirm</li>
                    </ol>
                    
                    <hr>
                    
                    <h6 class="small fw-bold text-muted mb-2">Code Format:</h6>
                    <ul class="small mb-0">
                        <li>6-8 characters long</li>
                        <li>Letters and numbers only</li>
                        <li>Case insensitive</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
{% endblock %}

{% block extra_js %}
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const codeInput = document.getElementById('{{ form.dismissal_code.id_for_label }}');
            const feedbackDiv = document.getElementById('code-validation-feedback');
            const submitBtn = document.getElementById('submit-btn');
            const form = document.getElementById('parent-arrival-form');
            
            let validationTimeout;
            let lastValidatedCode = '';
            
            // Real-time code validation
            codeInput.addEventListener('input', function() {
                const code = this.value.trim().toUpperCase();
                this.value = code; // Force uppercase
                
                clearTimeout(validationTimeout);
                
                if (code.length >= 3 && code !== lastValidatedCode) {
                    validationTimeout = setTimeout(() => validateCode(code), 500);
                } else if (code.length < 3) {
                    clearValidationFeedback();
                }
            });
            
            function validateCode(code) {
                if (code === lastValidatedCode) return;
                
                showValidationLoading();
                
                fetch('/dissmissal/api/validate-code/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: `code=${encodeURIComponent(code)}`
                })
                .then(response => response.json())
                .then(data => {
                    lastValidatedCode = code;
                    
                    if (data.valid) {
                        showValidationSuccess(data.student);
                    } else {
                        showValidationError(data.error);
                    }
                })
                .catch(error => {
                    console.error('Validation failed:', error);
                    showValidationError('Unable to validate code. Please try again.');
                });
            }
            
            function showValidationLoading() {
                feedbackDiv.innerHTML = `
                    <div class="d-flex align-items-center text-muted">
                        <div class="spinner-border spinner-border-sm me-2" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        Validating code...
                    </div>
                `;
            }
            
            function showValidationSuccess(student) {
                feedbackDiv.innerHTML = `
                    <div class="alert alert-success py-2 mb-0">
                        <i class="bi bi-check-circle me-2"></i>
                        <strong>Valid Code</strong> - ${student.name} (${student.grade}, ${student.teacher})
                        <br>
                        <small>Current Status: ${student.status_display}</small>
                    </div>
                `;
                
                codeInput.classList.remove('is-invalid');
                codeInput.classList.add('is-valid');
            }
            
            function showValidationError(error) {
                feedbackDiv.innerHTML = `
                    <div class="alert alert-danger py-2 mb-0">
                        <i class="bi bi-x-circle me-2"></i>
                        ${error}
                    </div>
                `;
                
                codeInput.classList.remove('is-valid');
                codeInput.classList.add('is-invalid');
            }
            
            function clearValidationFeedback() {
                feedbackDiv.innerHTML = '';
                codeInput.classList.remove('is-valid', 'is-invalid');
                lastValidatedCode = '';
            }
            
            // Form submission handling
            form.addEventListener('submit', function(e) {
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
                submitBtn.disabled = true;
            });
            
            // Focus on code input for quick entry
            codeInput.focus();
        });
    </script>
{% endblock %}
```

## Custom CSS Implementation

Create `dissmissal/static/dissmissal/css/main.css`:

```css
/* OpenDismissal Custom Styles */

/* CSS Variables for consistent theming */
:root {
    --od-primary: #0d6efd;
    --od-success: #198754;
    --od-info: #0dcaf0;
    --od-warning: #ffc107;
    --od-danger: #dc3545;
    --od-light: #f8f9fa;
    --od-dark: #212529;
    
    /* Mobile optimizations */
    --od-touch-target: 44px;
    --od-border-radius: 8px;
    --od-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

/* High contrast mode support */
@media (prefers-contrast: high) {
    :root {
        --od-primary: #0000ff;
        --od-success: #008000;
        --od-warning: #ff8c00;
        --od-danger: #ff0000;
    }
}

/* Loading animations */
@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.spin {
    animation: spin 1s linear infinite;
}

/* Mobile-first responsive utilities */
.btn-mobile {
    min-height: var(--od-touch-target);
    min-width: var(--od-touch-target);
    font-size: 16px !important; /* Prevent iOS zoom */
    font-weight: 500;
    border-radius: var(--od-border-radius);
    padding: 12px 20px;
}

.form-control-mobile {
    font-size: 16px !important; /* Prevent iOS zoom */
    min-height: var(--od-touch-target);
    border-radius: var(--od-border-radius);
    padding: 12px 16px;
}

/* Enhanced form controls for outdoor use */
.form-control:focus {
    border-color: var(--od-primary);
    box-shadow: 0 0 0 0.2rem rgba(13, 110, 253, 0.25);
}

.form-select:focus {
    border-color: var(--od-primary);
    box-shadow: 0 0 0 0.2rem rgba(13, 110, 253, 0.25);
}

/* Status-specific styling */
.status-waiting {
    background-color: #fff3cd;
    border-color: #ffecb5;
    color: #664d03;
}

.status-arrived {
    background-color: #d1ecf1;
    border-color: #bee5eb;
    color: #0c5460;
}

.status-picked-up {
    background-color: #d4edda;
    border-color: #c3e6cb;
    color: #155724;
}

/* Table enhancements for mobile */
.table-responsive {
    border-radius: var(--od-border-radius);
}

@media (max-width: 767.98px) {
    .table td {
        padding: 0.75rem 0.5rem;
        font-size: 14px;
    }
    
    .table th {
        padding: 0.75rem 0.5rem;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
}

/* Card enhancements */
.card {
    border: none;
    box-shadow: var(--od-shadow);
    border-radius: var(--od-border-radius);
}

.card-header {
    border-bottom: 1px solid rgba(0,0,0,0.125);
    background-color: rgba(0,0,0,0.03);
    font-weight: 600;
}

/* Statistics cards */
.card.bg-primary,
.card.bg-success,
.card.bg-info,
.card.bg-warning {
    background-image: linear-gradient(45deg, rgba(255,255,255,0.1) 25%, transparent 25%, transparent 50%, rgba(255,255,255,0.1) 50%, rgba(255,255,255,0.1) 75%, transparent 75%, transparent);
    background-size: 20px 20px;
}

/* Navigation enhancements */
.navbar-brand {
    font-weight: 700;
    font-size: 1.5rem;
}

@media (max-width: 991.98px) {
    .navbar-nav {
        padding-top: 1rem;
    }
    
    .navbar-nav .nav-link {
        padding: 0.75rem 1rem;
        border-radius: var(--od-border-radius);
        margin-bottom: 0.25rem;
    }
    
    .navbar-nav .nav-link.active {
        background-color: rgba(255,255,255,0.1);
    }
}

/* Alert message enhancements */
.alert {
    border: none;
    border-radius: var(--od-border-radius);
    box-shadow: var(--od-shadow);
}

.alert-dismissible .btn-close {
    padding: 0.75rem;
}

/* Modal enhancements for mobile */
@media (max-width: 575.98px) {
    .modal-dialog {
        margin: 1rem;
        max-width: none;
    }
    
    .modal-content {
        border-radius: var(--od-border-radius);
    }
}

/* Badge enhancements */
.badge {
    font-weight: 500;
    padding: 0.5em 0.75em;
    border-radius: 6px;
}

/* List group enhancements */
.list-group-item {
    border-left: none;
    border-right: none;
}

.list-group-item:first-child {
    border-top: none;
    border-top-left-radius: 0;
    border-top-right-radius: 0;
}

.list-group-item:last-child {
    border-bottom: none;
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
}

/* Pagination enhancements */
.pagination .page-link {
    border-radius: var(--od-border-radius);
    margin: 0 2px;
    border: 1px solid #dee2e6;
}

.pagination .page-item.active .page-link {
    background-color: var(--od-primary);
    border-color: var(--od-primary);
}

/* Loading states */
.loading {
    opacity: 0.6;
    pointer-events: none;
    position: relative;
}

.loading::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(255,255,255,0.8);
    display: flex;
    align-items: center;
    justify-content: center;
}

/* Accessibility enhancements */
.visually-hidden-focusable:not(:focus):not(:focus-within) {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    padding: 0 !important;
    margin: -1px !important;
    overflow: hidden !important;
    clip: rect(0, 0, 0, 0) !important;
    white-space: nowrap !important;
    border: 0 !important;
}

/* Focus indicators for keyboard navigation */
.btn:focus,
.form-control:focus,
.form-select:focus {
    outline: 2px solid var(--od-primary);
    outline-offset: 2px;
}

/* Print styles */
@media print {
    .navbar,
    .btn,
    .modal,
    .alert-dismissible .btn-close {
        display: none !important;
    }
    
    .card {
        border: 1px solid #dee2e6 !important;
        box-shadow: none !important;
    }
    
    .table {
        font-size: 12px;
    }
    
    .badge {
        border: 1px solid currentColor;
    }
}

/* Dark mode support */
@media (prefers-color-scheme: dark) {
    :root {
        --od-light: #343a40;
        --od-dark: #f8f9fa;
    }
    
    .card {
        background-color: #2d3748;
        color: #e2e8f0;
    }
    
    .table {
        --bs-table-bg: #2d3748;
        --bs-table-color: #e2e8f0;
    }
    
    .form-control {
        background-color: #4a5568;
        border-color: #718096;
        color: #e2e8f0;
    }
    
    .form-control:focus {
        background-color: #4a5568;
        border-color: var(--od-primary);
        color: #e2e8f0;
    }
}

/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
    
    .spin {
        animation: none;
    }
}

/* Custom utilities */
.user-select-all {
    user-select: all;
    -webkit-user-select: all;
    -moz-user-select: all;
    -ms-user-select: all;
}

.text-shadow {
    text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
}

.box-shadow-sm {
    box-shadow: 0 0.125rem 0.25rem rgba(0,0,0,0.075);
}

.box-shadow {
    box-shadow: var(--od-shadow);
}

.border-radius {
    border-radius: var(--od-border-radius);
}

/* Animation utilities */
.fade-in {
    animation: fadeIn 0.3s ease-in-out;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.slide-up {
    animation: slideUp 0.3s ease-out;
}

@keyframes slideUp {
    from { transform: translateY(20px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
}

/* Touch-friendly improvements */
@media (hover: none) and (pointer: coarse) {
    .btn:hover {
        transform: none;
    }
    
    .btn:active {
        transform: scale(0.98);
    }
    
    .card:hover {
        transform: none;
    }
}

/* iOS Safari specific fixes */
@supports (-webkit-touch-callout: none) {
    .form-control-mobile,
    .btn-mobile {
        -webkit-appearance: none;
        border-radius: var(--od-border-radius);
    }
    
    .navbar {
        -webkit-backdrop-filter: blur(10px);
        backdrop-filter: blur(10px);
    }
}
```

## JavaScript Implementation

Create `dissmissal/static/dissmissal/js/main.js`:

```javascript
/**
 * OpenDismissal Main JavaScript
 * Mobile-first interactive functionality for school dismissal management
 */

// Global utilities and configuration
const OpenDismissal = {
    config: {
        refreshInterval: 30000, // 30 seconds
        apiTimeout: 10000, // 10 seconds
        maxRetries: 3
    },
    
    // Utility functions
    utils: {
        // Get CSRF token for Django forms
        getCsrfToken() {
            const token = document.querySelector('[name=csrfmiddlewaretoken]');
            return token ? token.value : '';
        },
        
        // Show user feedback messages
        showMessage(message, type = 'info', duration = 5000) {
            const alertClass = {
                'success': 'alert-success',
                'error': 'alert-danger',
                'warning': 'alert-warning',
                'info': 'alert-info'
            }[type] || 'alert-info';
            
            const icon = {
                'success': 'bi-check-circle',
                'error': 'bi-exclamation-triangle',
                'warning': 'bi-exclamation-circle',
                'info': 'bi-info-circle'
            }[type] || 'bi-info-circle';
            
            const alertHtml = `
                <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
                    <i class="bi ${icon} me-2"></i>
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            `;
            
            // Insert at top of messages container or create one
            let container = document.getElementById('messages-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'messages-container';
                document.querySelector('main').insertBefore(container, document.querySelector('main').firstChild);
            }
            
            container.insertAdjacentHTML('afterbegin', alertHtml);
            
            // Auto-dismiss after duration
            if (duration > 0) {
                setTimeout(() => {
                    const alert = container.querySelector('.alert');
                    if (alert) {
                        const bsAlert = new bootstrap.Alert(alert);
                        bsAlert.close();
                    }
                }, duration);
            }
        },
        
        // Format time for display
        formatTime(date) {
            return new Intl.DateTimeFormat('en-US', {
                hour: 'numeric',
                minute: '2-digit',
                hour12: true
            }).format(date);
        },
        
        // Format relative time (e.g., "5 minutes ago")
        formatRelativeTime(date) {
            const now = new Date();
            const diff = now - date;
            const minutes = Math.floor(diff / 60000);
            
            if (minutes < 1) return 'Just now';
            if (minutes === 1) return '1 minute ago';
            if (minutes < 60) return `${minutes} minutes ago`;
            
            const hours = Math.floor(minutes / 60);
            if (hours === 1) return '1 hour ago';
            if (hours < 24) return `${hours} hours ago`;
            
            return date.toLocaleDateString();
        },
        
        // Debounce function for performance
        debounce(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        },
        
        // Throttle function for performance
        throttle(func, limit) {
            let inThrottle;
            return function() {
                const args = arguments;
                const context = this;
                if (!inThrottle) {
                    func.apply(context, args);
                    inThrottle = true;
                    setTimeout(() => inThrottle = false, limit);
                }
            };
        }
    },
    
    // API interaction methods
    api: {
        async request(url, options = {}) {
            const defaultOptions = {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                timeout: OpenDismissal.config.apiTimeout
            };
            
            // Add CSRF token for POST requests
            if (options.method === 'POST') {
                defaultOptions.headers['X-CSRFToken'] = OpenDismissal.utils.getCsrfToken();
            }
            
            const config = { ...defaultOptions, ...options };
            
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), config.timeout);
                
                const response = await fetch(url, {
                    ...config,
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                return data;
            } catch (error) {
                if (error.name === 'AbortError') {
                    throw new Error('Request timed out');
                }
                throw error;
            }
        },
        
        async validateDismissalCode(code) {
            return this.request('/dissmissal/api/validate-code/', {
                method: 'POST',
                body: `code=${encodeURIComponent(code)}`
            });
        },
        
        async getDashboardStatus() {
            return this.request('/dissmissal/api/status/');
        },
        
        async refreshDashboard(lastUpdate = null) {
            const url = lastUpdate 
                ? `/dissmissal/api/refresh/?last_update=${encodeURIComponent(lastUpdate)}`
                : '/dissmissal/api/refresh/';
            return this.request(url);
        },
        
        async quickPickup(studentId, notes = '') {
            return this.request('/dissmissal/api/quick-pickup/', {
                method: 'POST',
                body: `student_id=${studentId}&notes=${encodeURIComponent(notes)}`
            });
        }
    },
    
    // Initialize application
    init() {
        this.setupGlobalEventListeners();
        this.setupServiceWorker();
        this.setupNetworkMonitoring();
        
        // Initialize page-specific functionality
        this.initializePage();
    },
    
    setupGlobalEventListeners() {
        // Global form handling
        document.addEventListener('submit', function(e) {
            const form = e.target;
            if (form.tagName === 'FORM') {
                const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
                if (submitBtn && !submitBtn.disabled) {
                    const originalText = submitBtn.innerHTML;
                    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
                    submitBtn.disabled = true;
                    
                    // Re-enable button after a timeout in case form doesn't redirect
                    setTimeout(() => {
                        submitBtn.innerHTML = originalText;
                        submitBtn.disabled = false;
                    }, 10000);
                }
            }
        });
        
        // Global keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            // Alt + D = Dashboard
            if (e.altKey && e.key === 'd') {
                e.preventDefault();
                window.location.href = '/dissmissal/';
            }
            
            // Alt + A = Parent Arrival
            if (e.altKey && e.key === 'a') {
                e.preventDefault();
                window.location.href = '/dissmissal/arrival/';
            }
            
            // Alt + P = Student Pickup
            if (e.altKey && e.key === 'p') {
                e.preventDefault();
                window.location.href = '/dissmissal/pickup/';
            }
            
            // Escape = Close modals
            if (e.key === 'Escape') {
                const openModal = document.querySelector('.modal.show');
                if (openModal) {
                    const modalInstance = bootstrap.Modal.getInstance(openModal);
                    if (modalInstance) {
                        modalInstance.hide();
                    }
                }
            }
        });
        
        // Touch and gesture handling for mobile
        if ('ontouchstart' in window) {
            this.setupTouchHandling();
        }
    },
    
    setupTouchHandling() {
        // Prevent double-tap zoom on buttons
        document.addEventListener('touchend', function(e) {
            if (e.target.tagName === 'BUTTON' || e.target.closest('button')) {
                e.preventDefault();
            }
        });
        
        // Swipe gestures for navigation
        let touchStartX = 0;
        let touchStartY = 0;
        
        document.addEventListener('touchstart', function(e) {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
        });
        
        document.addEventListener('touchend', function(e) {
            if (!touchStartX || !touchStartY) return;
            
            const touchEndX = e.changedTouches[0].clientX;
            const touchEndY = e.changedTouches[0].clientY;
            
            const deltaX = touchEndX - touchStartX;
            const deltaY = touchEndY - touchStartY;
            
            // Only process horizontal swipes
            if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 100) {
                // Swipe right = back
                if (deltaX > 0 && window.history.length > 1) {
                    window.history.back();
                }
                // Could add swipe left for forward navigation
            }
            
            touchStartX = 0;
            touchStartY = 0;
        });
    },
    
    setupServiceWorker() {
        // Register service worker for offline functionality
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js').then(function(registration) {
                console.log('Service Worker registered successfully');
            }).catch(function(error) {
                console.log('Service Worker registration failed:', error);
            });
        }
    },
    
    setupNetworkMonitoring() {
        // Online/offline status monitoring
        window.addEventListener('online', () => {
            OpenDismissal.utils.showMessage('Connection restored', 'success');
            // Refresh data when back online
            if (typeof refreshDashboard === 'function') {
                refreshDashboard();
            }
        });
        
        window.addEventListener('offline', () => {
            OpenDismissal.utils.showMessage('You are offline. Some features may be limited.', 'warning', 0);
        });
        
        // Connection quality monitoring
        if ('connection' in navigator) {
            const connection = navigator.connection;
            
            if (connection.effectiveType === 'slow-2g' || connection.effectiveType === '2g') {
                OpenDismissal.utils.showMessage('Slow connection detected. Some features may be delayed.', 'warning');
            }
            
            connection.addEventListener('change', () => {
                if (connection.effectiveType === 'slow-2g' || connection.effectiveType === '2g') {
                    OpenDismissal.utils.showMessage('Connection quality changed. Performance may be affected.', 'info');
                }
            });
        }
    },
    
    initializePage() {
        const path = window.location.pathname;
        
        if (path.includes('/dissmissal/') && !path.includes('/admin/')) {
            if (path.endsWith('/') || path.includes('/dashboard')) {
                this.initDashboard();
            } else if (path.includes('/arrival/')) {
                this.initParentArrival();
            } else if (path.includes('/pickup/')) {
                this.initStudentPickup();
            }
        }
    },
    
    initDashboard() {
        // Dashboard-specific initialization handled in template
        console.log('Dashboard initialized');
    },
    
    initParentArrival() {
        // Parent arrival form enhancements
        const codeInput = document.querySelector('input[name="dismissal_code"]');
        if (codeInput) {
            // Auto-uppercase and format input
            codeInput.addEventListener('input', function(e) {
                let value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
                if (value.length > 8) value = value.substring(0, 8);
                e.target.value = value;
            });
            
            // Focus on load for quick entry
            codeInput.focus();
        }
    },
    
    initStudentPickup() {
        // Student pickup form enhancements
        console.log('Student pickup initialized');
    }
};

// Global utility functions (for backward compatibility)
function getCsrfToken() {
    return OpenDismissal.utils.getCsrfToken();
}

function showMessage(message, type, duration) {
    return OpenDismissal.utils.showMessage(message, type, duration);
}

function formatTime(date) {
    return OpenDismissal.utils.formatTime(date);
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    OpenDismissal.init();
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = OpenDismissal;
}
```

## Testing Requirements

Create basic JavaScript tests in `dissmissal/static/dissmissal/js/tests.js`:

```javascript
/**
 * Basic JavaScript tests for OpenDismissal
 * Run these in browser console or with testing framework
 */

const OpenDismissalTests = {
    runAll() {
        console.log('Running OpenDismissal JavaScript tests...');
        this.testUtilities();
        this.testAPI();
        this.testUIComponents();
        console.log('All tests completed');
    },
    
    testUtilities() {
        console.log('Testing utilities...');
        
        // Test CSRF token retrieval
        const token = OpenDismissal.utils.getCsrfToken();
        console.assert(typeof token === 'string', 'CSRF token should be string');
        
        // Test time formatting
        const now = new Date();
        const formatted = OpenDismissal.utils.formatTime(now);
        console.assert(formatted.includes(':'), 'Formatted time should contain colon');
        
        // Test debounce
        let counter = 0;
        const debouncedFn = OpenDismissal.utils.debounce(() => counter++, 100);
        debouncedFn();
        debouncedFn();
        debouncedFn();
        
        setTimeout(() => {
            console.assert(counter === 1, 'Debounced function should only execute once');
        }, 150);
        
        console.log('✓ Utilities tests passed');
    },
    
    testAPI() {
        console.log('Testing API methods...');
        
        // Test API request method exists
        console.assert(typeof OpenDismissal.api.request === 'function', 'API request method should exist');
        console.assert(typeof OpenDismissal.api.validateDismissalCode === 'function', 'Validate code method should exist');
        
        console.log('✓ API tests passed');
    },
    
    testUIComponents() {
        console.log('Testing UI components...');
        
        // Test message display
        OpenDismissal.utils.showMessage('Test message', 'info', 1000);
        
        setTimeout(() => {
            const messageContainer = document.getElementById('messages-container');
            console.assert(messageContainer !== null, 'Message container should be created');
        }, 100);
        
        console.log('✓ UI component tests passed');
    }
};

// Auto-run tests in development
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    setTimeout(() => {
        OpenDismissalTests.runAll();
    }, 2000);
}
```

## Integration Points & Success Criteria

### Dependencies Integration

**With Developer 1 (Backend Foundation):**
- ✅ **Model data:** Templates receive Student and PickupEvent data via context
- ✅ **API endpoints:** JavaScript calls validated endpoints for real-time updates
- ✅ **Static files:** CSS/JS served from proper Django static file structure

**With Developer 2 (Core Views):**
- ✅ **Context variables:** Templates use structured data from view functions
- ✅ **Form rendering:** Forms include proper Bootstrap widgets and validation
- ✅ **AJAX integration:** Frontend calls business logic endpoints seamlessly

### Required Deliverables

1. **✅ Base Template System**
   - Mobile-first responsive base template
   - Bootstrap 5.3 integration with custom CSS
   - Navigation with proper active states
   - Message handling system

2. **✅ Dashboard Interface**
   - Real-time status cards with statistics
   - Filterable student table with pagination
   - Auto-refresh functionality with countdown
   - Quick pickup modal for efficient workflow

3. **✅ Form Templates**
   - Parent arrival form with real-time validation
   - Student pickup form with status verification
   - Add student form with proper validation display
   - Mobile-optimized input controls

4. **✅ Custom CSS**
   - Mobile-first responsive design
   - High contrast for outdoor visibility
   - Touch-friendly interface elements
   - Accessibility compliance (WCAG 2.1)

5. **✅ JavaScript Functionality**
   - AJAX polling for dashboard updates
   - Real-time form validation
   - Offline functionality awareness
   - Touch and gesture support

6. **✅ Static File Organization**
   - Properly structured CSS and JavaScript files
   - Optimized for production deployment
   - Browser compatibility testing

### Testing Checklist

- [ ] Templates render correctly on all target devices
- [ ] Forms submit and validate properly
- [ ] AJAX updates work without page refresh
- [ ] CSS works in bright sunlight conditions
- [ ] Touch targets meet 44px minimum size
- [ ] Keyboard navigation works throughout
- [ ] Screen readers can navigate the interface
- [ ] Offline functionality degrades gracefully

### Performance Requirements

- [ ] Initial page load <3 seconds on 3G connection
- [ ] Dashboard updates complete in <1 second
- [ ] CSS and JavaScript files minified for production
- [ ] Images optimized for mobile bandwidth
- [ ] Caching headers properly configured

---

**Integration Timeline:**
1. **Days 2-4:** Base templates and CSS framework
2. **Days 5-7:** Dashboard interface with real-time updates
3. **Days 8-10:** Form templates with validation
4. **Days 11-12:** JavaScript polish and mobile optimization

**Questions for Team Coordination:**
1. **API response format:** Does the JSON structure match your JavaScript expectations?
2. **CSS framework:** Are there any specific Bootstrap components Developer 2 needs?
3. **Mobile testing:** Which devices should be prioritized for testing?
4. **Performance budget:** What are the target load times for different connection speeds?

Your frontend work creates the user experience that staff will interact with daily - prioritize usability and performance!