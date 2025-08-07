"""
Custom middleware for OpenDismissal project.

Provides SSL redirect exemptions for health check endpoints.
"""

import re
from django.conf import settings
from django.http import HttpResponsePermanentRedirect
from django.utils.deprecation import MiddlewareMixin


class SSLRedirectExemptMiddleware(MiddlewareMixin):
    """
    Custom SSL redirect middleware that allows exemptions for specific URLs.
    
    This replaces Django's SecurityMiddleware SSL redirect functionality
    but adds support for exempting certain URLs from SSL redirects.
    Primarily used to allow Kubernetes health check probes to use HTTP
    while maintaining HTTPS for user-facing traffic.
    """
    
    def process_request(self, request):
        """Process incoming requests for SSL redirect logic."""
        # Only perform SSL redirect logic if SECURE_SSL_REDIRECT is enabled
        if not getattr(settings, 'SECURE_SSL_REDIRECT', False):
            return None
            
        # Check if this URL should be exempt from SSL redirects
        exempt_patterns = getattr(settings, 'SECURE_SSL_REDIRECT_EXEMPT', [])
        for pattern in exempt_patterns:
            if re.match(pattern, request.path):
                # This URL is exempt from SSL redirects
                return None
                
        # Check if the request is already secure
        if self._is_secure(request):
            return None
            
        # Not secure and not exempt - redirect to HTTPS
        return self._redirect_to_https(request)
    
    def _is_secure(self, request):
        """Check if the request is secure (HTTPS)."""
        # Check for the standard HTTPS indicator
        if request.is_secure():
            return True
            
        # Check for proxy headers (e.g., from load balancer)
        proxy_header = getattr(settings, 'SECURE_PROXY_SSL_HEADER', None)
        if proxy_header:
            header_name, header_value = proxy_header
            if request.META.get(header_name) == header_value:
                return True
                
        return False
    
    def _redirect_to_https(self, request):
        """Redirect HTTP request to HTTPS."""
        # Build the HTTPS URL
        host = request.get_host()
        https_url = f"https://{host}{request.get_full_path()}"
        
        return HttpResponsePermanentRedirect(https_url)