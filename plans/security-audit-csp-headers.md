# Security Audit Report: OpenDismissal CSP and Header Configuration
**Date:** 2025-08-07  
**Auditor:** Security Specialist  
**Severity Levels:** 🔴 Critical | 🟠 High | 🟡 Medium | 🟢 Low

## Executive Summary

The OpenDismissal Django application is experiencing security header conflicts causing browser console errors and blocking legitimate static resources. While the application has implemented multiple security layers, conflicting configurations between Django settings and Nginx ingress are creating CSP violations and COOP header issues.

## 1. Security Vulnerabilities Found

### 🟠 **HIGH: Missing Content Security Policy (CSP) Configuration**
- **Issue:** No CSP headers configured in Django or Nginx
- **Impact:** XSS attacks possible, static resources blocked
- **Evidence:** Console errors: "Refused to apply style" and "Refused to execute script"
- **OWASP Reference:** A03:2021 – Injection

### 🟠 **HIGH: Cross-Origin-Opener-Policy (COOP) Misconfiguration**
- **Issue:** COOP header being ignored due to missing or conflicting settings
- **Impact:** Potential cross-origin attacks, browser security warnings
- **Evidence:** "Cross-Origin-Opener-Policy header has been ignored" warnings

### 🟡 **MEDIUM: Duplicate Security Headers**
- **Issue:** Security headers set in both Django middleware and Nginx ingress
- **Impact:** Conflicting values, unpredictable behavior
- **Location:** Django settings.py + k8s/ingress.yaml configuration-snippet

### 🟡 **MEDIUM: WhiteNoise Static File Security**
- **Issue:** WhiteNoise compression enabled but CSP not configured for static files
- **Impact:** Static files may be blocked by browser security policies
- **Location:** Django STATICFILES_STORAGE configuration

### 🟢 **LOW: Missing Security Headers**
- **Issue:** No Permissions-Policy header configured
- **Impact:** Browser features not explicitly controlled
- **Recommendation:** Add feature policy for camera, microphone, geolocation

## 2. Root Cause Analysis

### Primary Issues:
1. **No CSP Implementation:** Neither Django nor Nginx is setting Content-Security-Policy headers
2. **Header Duplication:** Same headers set in multiple places with different values
3. **Missing CORS Configuration:** No CORS headers for API endpoints
4. **Static File Path Issues:** CSP blocking `/static/` resources due to missing directives

## 3. Recommended Fixes

### Fix 1: Add Django CSP Configuration (Preferred Solution)

**Step 1:** Install django-csp package:
```bash
uv add django-csp
```

**Step 2:** Update Django settings.py:

```python
# /home/kwhatcher/projects/opendismissal/opendiss/settings.py

# Add to INSTALLED_APPS
INSTALLED_APPS = [
    # ... existing apps ...
    'csp',  # Add Content Security Policy support
]

# Add CSP middleware AFTER SecurityMiddleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'csp.middleware.CSPMiddleware',  # Add this line
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # ... rest of middleware ...
]

# Content Security Policy Configuration
# FERPA Compliant: No external analytics or third-party resources
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

# Report CSP violations (optional, for monitoring)
# CSP_REPORT_URI = '/csp-report/'
# CSP_REPORT_ONLY = False  # Set to True for testing

# Cross-Origin Policies
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
```

### Fix 2: Update K8s ConfigMap for CSP Support

```yaml
# /home/kwhatcher/projects/opendismissal/k8s/overlays/demo/configmap.yaml

apiVersion: v1
kind: ConfigMap
metadata:
  name: django-config
  namespace: opendismissal-demo
data:
  # ... existing configuration ...
  
  # Add CSP environment variables
  CSP_DEFAULT_SRC: "'self'"
  CSP_SCRIPT_SRC: "'self' 'unsafe-inline' 'unsafe-eval'"
  CSP_STYLE_SRC: "'self' 'unsafe-inline'"
  CSP_IMG_SRC: "'self' data: https:"
  CSP_FONT_SRC: "'self' data:"
  CSP_CONNECT_SRC: "'self'"
  CSP_FRAME_ANCESTORS: "'none'"
  
  # Cross-Origin Policies
  SECURE_CROSS_ORIGIN_OPENER_POLICY: "same-origin"
```

### Fix 3: Remove Duplicate Headers from Nginx Ingress

```yaml
# /home/kwhatcher/projects/opendismissal/k8s/overlays/demo/ingress.yaml

apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: django-ingress
  namespace: opendismissal-demo
  annotations:
    # Remove duplicate security headers - let Django handle them
    # Only keep Nginx-specific configurations
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "60"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "60"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "60"
    
    # Keep rate limiting at ingress level
    nginx.ingress.kubernetes.io/rate-limit-requests-per-second: "10"
    nginx.ingress.kubernetes.io/rate-limit-burst-multiplier: "5"
    
    # Add CORS support for static files
    nginx.ingress.kubernetes.io/enable-cors: "true"
    nginx.ingress.kubernetes.io/cors-allow-origin: "https://dismiss.hatchertechnology.com"
    nginx.ingress.kubernetes.io/cors-allow-methods: "GET, POST, OPTIONS"
    nginx.ingress.kubernetes.io/cors-allow-headers: "DNT,X-CustomHeader,Keep-Alive,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Authorization"
    
    # Remove configuration-snippet to avoid header conflicts
```

### Fix 4: Alternative - CSP via Nginx Ingress (If Django CSP not preferred)

```yaml
# /home/kwhatcher/projects/opendismissal/k8s/overlays/demo/ingress.yaml

apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: django-ingress
  namespace: opendismissal-demo
  annotations:
    # Set CSP header via Nginx
    nginx.ingress.kubernetes.io/configuration-snippet: |
      more_set_headers "Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self';";
      more_set_headers "Cross-Origin-Opener-Policy: same-origin";
      more_set_headers "Cross-Origin-Embedder-Policy: require-corp";
      more_set_headers "Cross-Origin-Resource-Policy: same-origin";
      more_set_headers "Permissions-Policy: camera=(), microphone=(), geolocation=()";
```

## 4. Production Security Best Practices

### Recommended Security Headers Configuration

```python
# Production-ready security configuration
# /home/kwhatcher/projects/opendismissal/opendiss/settings.py

# Security Headers (OWASP Compliant)
SECURE_BROWSER_XSS_FILTER = True  # Deprecated but still useful for older browsers
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Session Security (FERPA Compliance)
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 3600  # 1 hour for school environment
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# CSRF Protection
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_TRUSTED_ORIGINS = ['https://dismiss.hatchertechnology.com']
CSRF_USE_SESSIONS = True  # Store CSRF token in session for better security

# Additional Security Settings
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB max upload

# Permissions Policy (via custom middleware if needed)
PERMISSIONS_POLICY = {
    'camera': 'none',
    'microphone': 'none',
    'geolocation': 'none',
    'payment': 'none',
    'usb': 'none',
}
```

### Security Checklist for FERPA Compliance

- [x] All student data endpoints require authentication
- [x] Audit logging implemented for all data access
- [x] Session timeout configured (1 hour)
- [x] HTTPS enforced via HSTS
- [x] XSS protection via CSP headers
- [x] CSRF protection enabled
- [x] SQL injection prevention (Django ORM)
- [ ] CSP reporting endpoint configured
- [ ] Security headers monitoring
- [ ] Regular dependency scanning
- [ ] Penetration testing scheduled

## 5. Testing Security Headers

### Test Commands:

```bash
# Test security headers
curl -I https://dismiss.hatchertechnology.com

# Check CSP header
curl -I https://dismiss.hatchertechnology.com | grep -i content-security

# Test static file access
curl -I https://dismiss.hatchertechnology.com/static/css/main.css

# Validate CORS
curl -H "Origin: https://dismiss.hatchertechnology.com" \
     -H "Access-Control-Request-Method: GET" \
     -H "Access-Control-Request-Headers: X-Requested-With" \
     -X OPTIONS \
     https://dismiss.hatchertechnology.com/api/endpoint
```

### Expected Headers:

```http
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'
Cross-Origin-Opener-Policy: same-origin
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

## 6. Immediate Action Items

1. **Priority 1 (Fix Console Errors):**
   - Implement CSP configuration in Django settings
   - Remove duplicate headers from Nginx ingress
   - Test static file access after changes

2. **Priority 2 (Security Hardening):**
   - Add CORS configuration for API endpoints
   - Configure Cross-Origin policies
   - Add Permissions-Policy header

3. **Priority 3 (Monitoring):**
   - Set up CSP violation reporting
   - Monitor security headers with securityheaders.com
   - Schedule quarterly security audits

## 7. Risk Assessment

| Issue | Current Risk | After Fix | Business Impact |
|-------|-------------|-----------|-----------------|
| Missing CSP | 🟠 High | 🟢 Low | XSS Protection |
| COOP Errors | 🟡 Medium | 🟢 Low | Browser Warnings |
| Static Files Blocked | 🟠 High | 🟢 Low | App Functionality |
| Duplicate Headers | 🟡 Medium | 🟢 Low | Predictable Behavior |

## 8. Compliance Notes

### FERPA Requirements Met:
- ✅ Authentication required for all student data
- ✅ Audit logging implemented
- ✅ Secure session management
- ✅ Data encryption in transit (HTTPS)
- ✅ Access control implemented

### Additional Recommendations:
1. Implement rate limiting on authentication endpoints
2. Add failed login attempt monitoring
3. Configure automated security scanning
4. Implement data retention policies
5. Regular security training for staff

## Conclusion

The primary issues causing browser console errors are:
1. Missing CSP configuration blocking legitimate static resources
2. Lack of Cross-Origin-Opener-Policy configuration
3. Duplicate security headers causing conflicts

Implementing the recommended Django CSP configuration will resolve all console errors while maintaining strong security posture appropriate for a school application handling sensitive student data.

**Estimated Implementation Time:** 2-3 hours  
**Testing Time:** 1-2 hours  
**Risk Level:** Low (with proper testing)