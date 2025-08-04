# OpenDismissal MVP Implementation Plan

**Author:** Riley Thompson  
**Date:** August 4, 2025  
**Purpose:** Minimal viable product for principal demonstration  

## Overview

This plan outlines the implementation of an absolute minimal MVP for OpenDismissal to demonstrate core functionality to the school principal. The focus is on creating a working prototype that shows the essential student dismissal workflow without complex features or production-ready architecture.

**What we're building:** A simple web interface where staff can mark parent arrivals, track student pickups, and view real-time dismissal status.

## Core Functionality (Minimal)

### 1. Student Management
- Add students with dismissal codes
- View student list
- Basic student information (name, dismissal code)

### 2. Dismissal Process
- Mark parent arrival by dismissal code
- Mark student as picked up
- View current dismissal status

### 3. Dashboard
- Simple list view of all students
- Status indicators (waiting, parent arrived, picked up)
- Basic timestamps

## Technical Implementation

### Models Required
```python
# Student model
class Student:
    - name (CharField)
    - dismissal_code (CharField, unique)
    - created_at (DateTimeField)

# PickupEvent model  
class PickupEvent:
    - student (ForeignKey to Student)
    - status (CharField: choices=['waiting', 'parent_arrived', 'picked_up'])
    - timestamp (DateTimeField)
    - notes (TextField, optional)
```

### Views and Functions

#### `dashboard_view(request)`
Displays all students and their current pickup status. Shows a simple table with student names, dismissal codes, and current status.

#### `mark_parent_arrival(request)`
Form view to enter a dismissal code and mark parent as arrived. Updates the PickupEvent status from 'waiting' to 'parent_arrived'.

#### `mark_student_pickup(request)`
Form view to mark a student as picked up. Updates PickupEvent status to 'picked_up' and records timestamp.

#### `add_student(request)`
Simple form to add new students to the system with name and dismissal code.

### URLs Structure
```
/ - Dashboard (main view)
/parent-arrived/ - Mark parent arrival form
/student-pickup/ - Mark pickup form  
/add-student/ - Add student form
```

### Templates
- `base.html` - Simple Bootstrap layout
- `dashboard.html` - Main status table
- `forms.html` - Generic form template for all actions

## Files to Create/Modify

### New Files
- `dissmissal/templates/dissmissal/base.html`
- `dissmissal/templates/dissmissal/dashboard.html`
- `dissmissal/templates/dissmissal/form.html`
- `dissmissal/forms.py`
- `dissmissal/urls.py`

### Files to Modify
- `dissmissal/models.py` - Add Student and PickupEvent models
- `dissmissal/views.py` - Add all view functions
- `dissmissal/admin.py` - Basic admin registration
- `opendiss/settings.py` - Add dissmissal to INSTALLED_APPS
- `opendiss/urls.py` - Include dissmissal URLs

## Test Coverage

### Model Tests
- `test_student_creation()` - Verify student can be created with valid data
- `test_dismissal_code_uniqueness()` - Ensure dismissal codes are unique
- `test_pickup_event_creation()` - Verify pickup events link correctly to students

### View Tests  
- `test_dashboard_displays_students()` - Verify dashboard shows all students
- `test_mark_parent_arrival_updates_status()` - Confirm status changes when parent arrives
- `test_mark_pickup_completes_process()` - Verify pickup completion workflow
- `test_invalid_dismissal_code_handling()` - Check error handling for bad codes

### Integration Tests
- `test_complete_dismissal_workflow()` - Full process from student creation to pickup
- `test_multiple_students_handling()` - Verify system works with multiple students

## Setup Steps

1. Add `dissmissal` to INSTALLED_APPS
2. Create and run migrations for new models
3. Create superuser for admin access
4. Add basic URL routing
5. Create minimal templates with Bootstrap
6. Implement view functions
7. Add basic forms for user input
8. Test complete workflow manually

## Success Criteria

**Demo-ready when:**
- Principal can see list of students awaiting pickup
- Staff can mark when parents arrive
- Staff can mark when students are picked up  
- Status updates are visible immediately
- Basic error handling prevents crashes
- Clean, professional appearance

## Deliberately Excluded (Not MVP)

- User authentication (will use Django admin login)
- Real-time WebSocket updates
- Mobile optimization
- Audit logging
- Parent notification system
- Advanced reporting
- Bulk operations
- Data import/export
- Production security measures

## Time Estimate

**2-3 hours total:**
- Models and migrations: 30 minutes
- Basic views and forms: 60 minutes  
- Templates and styling: 45 minutes
- Testing and refinement: 30 minutes

This MVP focuses purely on demonstrating the core concept to stakeholders while keeping implementation as simple as possible.