# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenDismissal is a Django-based school dismissal management system that replaces paper-based student pickup systems with a secure, real-time digital solution. The system provides staff interfaces for logging parent arrivals and tracking student pickups with full audit logging and FERPA compliance.

## Very important directions

__NEVER check in secrets, API keys, or passwords. Use environment variables via .env files. Ensure that any secrets are excluded from version control (see .gitignore).__

## Development Commands

All Python commands should be prefixed with `uv run`:

```bash
# Development server
uv run python manage.py runserver

# Database operations
uv run python manage.py makemigrations
uv run python manage.py migrate

# Create superuser
uv run python manage.py createsuperuser

# Generate demo data (custom command)
uv run python manage.py generate_demo_data

# Linting and formatting
uv run ruff check .
uv run ruff format .
uv run djlint --check --reformat .

# Security scanning
uv run bandit -r .
uv run safety check

# Testing
uv run python manage.py test
```

## Architecture

### Django Project Structure
- **opendiss/**: Main Django project (settings, URLs, WSGI/ASGI)
- **dissmissal/**: Core app handling dismissal logic (note: intentional spelling with double 's')

### Technology Stack
- **Backend**: Django 5.2+ with Django Rest Framework
- **Database**: PostgreSQL with psycopg
- **Authentication**: django-allauth with individual staff logins
- **Real-time**: Django Channels with WebSockets for live updates
- **Caching**: Redis for session storage and message broker
- **Frontend**: React with Tailwind CSS (separate from Django templates)
- **Configuration**: python-decouple with .env files
- **Logging**: Loguru for audit trail requirements

### Core Models Architecture
The system centers around these key models:
- **Student**: Name and dismissal code mapping
- **DismissalCode**: Unique codes for parent verification
- **PickupEvent**: Real-time tracking of parent arrivals and student pickups
- **Staff**: Individual logins with role-based permissions for accountability

### Security Requirements
- All non-public endpoints protected with `@login_required`
- Environment-based configuration (never hardcode secrets)
- FERPA and FOIA compliance for student data
- Complete audit logging of all actions
- Production security headers configured

### Real-time Features
Uses Django Channels for WebSocket connections to provide:
- Live dashboard of parent arrivals
- Real-time pickup status updates
- Staff coordination without manual refresh


## Infrastructure and Deployment

Will be deployed to Digital Ocean using their MCP. `doctl` cli is installed and configured if MCP doesn't cover a needed feature.

Should be containerized using podman with the image hosted on github container registry.

Kubernetes (K8s) should be used for hosting the application. Digital Ocean's managed kubernetes service should be used.

The K8s MCP server is available  and should be used for managing the cluster.

Secrets should be written to .env files locally as those are not checked into git. In production, secrets should be deployed via Kubernetes secrets.

Local build and deployment is ok for now, but eventually should be deployed via ArgoCD or similar.



## Development Setup Notes

### Environment Configuration
Settings use python-decouple for environment variables. Create `.env` file for local development with database credentials, secret keys, and debug settings.

### Database
Production uses PostgreSQL. Development can use SQLite but should test PostgreSQL compatibility for any database-specific features.

### Code Standards
- 100-character line length (configured in pyproject.toml)
- Google-style docstrings for functions/classes
- Conventional Commits for commit messages
- Unit tests required for all new functionality
- The dismissal app should remain reusable across different school implementations

### Docker Setup
Project includes Docker and Docker Compose for local development and deployment. The setup handles PostgreSQL, Redis, and Django services with proper networking.

## Important Notes

- The `dissmissal` app name contains an intentional double 's' - do not "fix" this spelling
- All endpoints handling student data must include audit logging
- Real-time updates are critical for staff coordination during dismissal periods
- System must handle concurrent access from multiple staff members
- Mobile-first design for staff smartphone usage during outdoor dismissal periods


## Acronyms
- **K8s**: Kubernetes
- **MCP**: Managed Container Platform
- **FERPA**: Family Educational Rights and Privacy Act
- **FOIA**: Freedom of Information Act
- **ORR**: Open Records Request
- **DO**: Digital Ocean
- **WSGI**: Web Server Gateway Interface
- **ASGI**: Asynchronous Server Gateway Interface
- **DRF**: Django Rest Framework
- **CI/CD**: Continuous Integration / Continuous Deployment
- **API**: Application Programming Interface
- **SSL/TLS**: Secure Sockets Layer / Transport Layer Security
- **CRUD**: Create, Read, Update, Delete
- **JSON**: JavaScript Object Notation
- **HTML**: HyperText Markup Language
- **CSS**: Cascading Style Sheets
- **JS**: JavaScript
- **CLI**: Command Line Interface
- 