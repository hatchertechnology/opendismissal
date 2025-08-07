"""
Security middleware for OpenDismissal application.
Implements secure Content Security Policy without unsafe-inline/unsafe-eval.
"""

import hashlib
import secrets
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings


class SecureCSPMiddleware(MiddlewareMixin):
    """
    Middleware to add secure Content Security Policy headers.
    Generates per-request nonces for inline scripts/styles when absolutely necessary.
    """
    
    def process_request(self, request):
        """Generate CSP nonce for this request."""
        # Generate a secure random nonce for this request
        nonce = secrets.token_urlsafe(32)
        request.csp_nonce = nonce
        return None
    
    def process_response(self, request, response):
        """Add CSP headers to response."""
        # Skip if in development mode or if header already set
        if settings.DEBUG or 'Content-Security-Policy' in response:
            return response
        
        # Get nonce if available
        nonce = getattr(request, 'csp_nonce', None)
        
        # Build CSP directives
        csp_directives = []
        
        # Default source - only from same origin
        csp_directives.append("default-src 'self'")
        
        # Scripts - only from same origin, no unsafe-inline or unsafe-eval
        # If nonce is needed for specific inline scripts, add it here
        if nonce and getattr(settings, 'CSP_ALLOW_NONCE', False):
            csp_directives.append(f"script-src 'self' 'nonce-{nonce}'")
        else:
            csp_directives.append("script-src 'self'")
        
        # Styles - only from same origin
        # If nonce is needed for specific inline styles, add it here
        if nonce and getattr(settings, 'CSP_ALLOW_NONCE', False):
            csp_directives.append(f"style-src 'self' 'nonce-{nonce}'")
        else:
            csp_directives.append("style-src 'self'")
        
        # Images - self and data URIs only
        csp_directives.append("img-src 'self' data:")
        
        # Fonts - only from same origin
        csp_directives.append("font-src 'self'")
        
        # Connections - self and WebSocket for real-time updates
        allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])
        connect_sources = ["'self'"]
        
        # Add WebSocket origins for real-time features
        for host in allowed_hosts:
            if host and host != '*':
                connect_sources.append(f"wss://{host}")
                connect_sources.append(f"https://{host}")
        
        csp_directives.append(f"connect-src {' '.join(connect_sources)}")
        
        # Frames - deny all framing (clickjacking protection)
        csp_directives.append("frame-ancestors 'none'")
        
        # Forms - only submit to same origin
        csp_directives.append("form-action 'self'")
        
        # Base URI - only same origin
        csp_directives.append("base-uri 'self'")
        
        # Object sources - none (no plugins)
        csp_directives.append("object-src 'none'")
        
        # Media sources - self only
        csp_directives.append("media-src 'self'")
        
        # Worker sources - self only
        csp_directives.append("worker-src 'self'")
        
        # Manifest - self only
        csp_directives.append("manifest-src 'self'")
        
        # Upgrade insecure requests
        if not settings.DEBUG:
            csp_directives.append("upgrade-insecure-requests")
        
        # Block all mixed content
        csp_directives.append("block-all-mixed-content")
        
        # Join all directives
        csp_header = "; ".join(csp_directives)
        
        # Set the CSP header
        response['Content-Security-Policy'] = csp_header
        
        # Add report-only header for testing (can be removed after validation)
        if getattr(settings, 'CSP_REPORT_ONLY', False):
            response['Content-Security-Policy-Report-Only'] = csp_header
            
        return response


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add additional security headers beyond CSP.
    """
    
    def process_response(self, request, response):
        """Add security headers to response."""
        
        # Strict Transport Security
        if not settings.DEBUG:
            max_age = getattr(settings, 'SECURE_HSTS_SECONDS', 31536000)
            hsts_header = f"max-age={max_age}"
            
            if getattr(settings, 'SECURE_HSTS_INCLUDE_SUBDOMAINS', True):
                hsts_header += "; includeSubDomains"
            
            if getattr(settings, 'SECURE_HSTS_PRELOAD', True):
                hsts_header += "; preload"
                
            response['Strict-Transport-Security'] = hsts_header
        
        # X-Content-Type-Options
        response['X-Content-Type-Options'] = 'nosniff'
        
        # X-Frame-Options (redundant with CSP frame-ancestors but good for compatibility)
        response['X-Frame-Options'] = 'DENY'
        
        # Referrer Policy
        response['Referrer-Policy'] = getattr(
            settings, 
            'SECURE_REFERRER_POLICY', 
            'strict-origin-when-cross-origin'
        )
        
        # Permissions Policy (formerly Feature Policy)
        permissions = [
            "accelerometer=()",
            "ambient-light-sensor=()",
            "autoplay=()",
            "battery=()",
            "camera=()",
            "display-capture=()",
            "document-domain=()",
            "encrypted-media=()",
            "fullscreen=(self)",
            "geolocation=()",
            "gyroscope=()",
            "interest-cohort=()",  # Disable FLoC
            "magnetometer=()",
            "microphone=()",
            "midi=()",
            "payment=()",
            "picture-in-picture=()",
            "screen-wake-lock=()",
            "sync-xhr=()",
            "usb=()",
            "web-share=()",
            "xr-spatial-tracking=()"
        ]
        response['Permissions-Policy'] = ", ".join(permissions)
        
        # Cross-Origin Resource Policy
        response['Cross-Origin-Resource-Policy'] = 'same-origin'
        
        # Cross-Origin Opener Policy
        response['Cross-Origin-Opener-Policy'] = 'same-origin'
        
        # Cross-Origin Embedder Policy (if needed for SharedArrayBuffer)
        # response['Cross-Origin-Embedder-Policy'] = 'require-corp'
        
        return response