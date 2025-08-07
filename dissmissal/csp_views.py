"""
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
