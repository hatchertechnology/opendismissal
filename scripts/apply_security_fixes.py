#!/usr/bin/env python3
"""
Apply security fixes to Django settings for CSP and COOP configuration.
This script adds the necessary security configurations to resolve browser console errors.

Usage:
    uv run python scripts/apply_security_fixes.py
"""

import os
import sys
from pathlib import Path

def add_csp_to_requirements():
    """Add django-csp to pyproject.toml dependencies."""
    pyproject_path = Path("pyproject.toml")
    
    if not pyproject_path.exists():
        print("❌ pyproject.toml not found")
        return False
    
    content = pyproject_path.read_text()
    
    # Check if django-csp is already added
    if "django-csp" in content:
        print("✅ django-csp already in dependencies")
        return True
    
    # Find the dependencies section and add django-csp
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.strip().startswith('"django>='):
            # Add django-csp after django
            lines.insert(i + 1, '    "django-csp>=3.7",')
            print("✅ Added django-csp to dependencies")
            break
    
    pyproject_path.write_text('\n'.join(lines))
    return True

def update_django_settings():
    """Update Django settings.py with CSP configuration."""
    settings_path = Path("opendiss/settings.py")
    
    if not settings_path.exists():
        print("❌ settings.py not found")
        return False
    
    content = settings_path.read_text()
    
    # Check if CSP is already configured
    if "'csp'" in content or '"csp"' in content:
        print("✅ CSP already configured in settings.py")
        return True
    
    # CSP configuration to add
    csp_config = '''
# Content Security Policy Configuration (Added for security audit fixes)
# Resolves browser console errors and implements OWASP best practices
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = (
    "'self'",
    "'unsafe-inline'",  # Required for Django admin
    "'unsafe-eval'",    # Required for some Django admin features
)
CSP_STYLE_SRC = (
    "'self'",
    "'unsafe-inline'",  # Required for Django admin styles
)
CSP_FONT_SRC = ("'self'", "data:")
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_CONNECT_SRC = ("'self'",)  # For AJAX/WebSocket connections
CSP_FRAME_ANCESTORS = ("'none'",)  # Equivalent to X-Frame-Options: DENY
CSP_BASE_URI = ("'self'",)
CSP_FORM_ACTION = ("'self'",)
CSP_UPGRADE_INSECURE_REQUESTS = not DEBUG  # Upgrade HTTP to HTTPS in production

# Cross-Origin Policies (fixes COOP browser warnings)
SECURE_CROSS_ORIGIN_OPENER_POLICY = config("SECURE_CROSS_ORIGIN_OPENER_POLICY", default="same-origin")

# Additional security hardening
DATA_UPLOAD_MAX_MEMORY_SIZE = config("DATA_UPLOAD_MAX_MEMORY_SIZE", default=5242880, cast=int)  # 5MB
SESSION_EXPIRE_AT_BROWSER_CLOSE = config("SESSION_EXPIRE_AT_BROWSER_CLOSE", default=True, cast=bool)
CSRF_USE_SESSIONS = config("CSRF_USE_SESSIONS", default=True, cast=bool)  # Store CSRF in session

# Permissions Policy (for additional browser feature control)
# Note: This would require custom middleware to implement
PERMISSIONS_POLICY = {
    "camera": "none",
    "microphone": "none",
    "geolocation": "none",
    "payment": "none",
    "usb": "none",
}
'''

    # Add CSP to INSTALLED_APPS
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'INSTALLED_APPS = [' in line:
            # Find the end of third-party apps section
            for j in range(i, len(lines)):
                if '# Local apps' in lines[j]:
                    lines.insert(j, '    "csp",  # Content Security Policy support')
                    print("✅ Added 'csp' to INSTALLED_APPS")
                    break
            break
    
    # Add CSP middleware
    for i, line in enumerate(lines):
        if '"django.middleware.security.SecurityMiddleware"' in line:
            lines.insert(i + 1, '    "csp.middleware.CSPMiddleware",  # Content Security Policy')
            print("✅ Added CSP middleware")
            break
    
    # Add CSP configuration at the end of the file
    lines.append("")
    lines.append(csp_config)
    print("✅ Added CSP configuration settings")
    
    # Write back the updated content
    settings_path.write_text('\n'.join(lines))
    return True

def create_csp_report_view():
    """Create a CSP violation report endpoint."""
    views_content = '''"""
CSP Violation Reporting View
Handles Content Security Policy violation reports from browsers.
"""

import json
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# Set up CSP violation logger
csp_logger = logging.getLogger("security.csp")

@csrf_exempt
@require_POST
def csp_report_view(request):
    """
    Receive and log CSP violation reports.
    Browsers send these when content violates the Content Security Policy.
    """
    try:
        if request.content_type == 'application/csp-report':
            report = json.loads(request.body.decode('utf-8'))
            csp_report = report.get('csp-report', {})
            
            # Log the violation
            csp_logger.warning(
                "CSP Violation: %(directive)s - %(blocked_uri)s on %(document_uri)s",
                {
                    'directive': csp_report.get('violated-directive', 'unknown'),
                    'blocked_uri': csp_report.get('blocked-uri', 'unknown'),
                    'document_uri': csp_report.get('document-uri', 'unknown'),
                },
                extra={
                    'full_report': csp_report,
                    'user': request.user.username if request.user.is_authenticated else 'anonymous',
                    'ip_address': request.META.get('REMOTE_ADDR'),
                }
            )
    except Exception as e:
        csp_logger.error(f"Error processing CSP report: {e}")
    
    return HttpResponse(status=204)  # No content response
'''
    
    # Create the CSP report view file
    views_path = Path("dissmissal/csp_views.py")
    views_path.write_text(views_content)
    print("✅ Created CSP report view")
    
    # Add URL pattern
    urls_content = '''
# Add to dissmissal/urls.py:
# from .csp_views import csp_report_view
# 
# urlpatterns = [
#     # ... existing patterns ...
#     path('csp-report/', csp_report_view, name='csp_report'),
# ]
'''
    print("ℹ️  Remember to add CSP report URL to dissmissal/urls.py")
    print(urls_content)
    
    return True

def main():
    """Main function to apply all security fixes."""
    print("🔒 Applying Security Fixes for OpenDismissal")
    print("=" * 50)
    
    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    print("\n1. Adding django-csp to dependencies...")
    add_csp_to_requirements()
    
    print("\n2. Updating Django settings...")
    update_django_settings()
    
    print("\n3. Creating CSP report endpoint...")
    create_csp_report_view()
    
    print("\n✅ Security fixes applied successfully!")
    print("\n📝 Next steps:")
    print("1. Run: uv sync")
    print("2. Update dissmissal/urls.py with CSP report endpoint")
    print("3. Test with: uv run python manage.py runserver")
    print("4. Deploy updated ConfigMap and Ingress to Kubernetes")
    print("\n🔍 Test security headers at: https://securityheaders.com")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())