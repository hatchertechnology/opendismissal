# Security Policy

## Critical Security Configuration

This document outlines the security measures implemented in the OpenDismissal application, which handles FERPA-protected student data.

### 🔐 Secret Management

**CRITICAL**: Never commit secrets to version control!

1. **Local Development**: Use `.env` files (gitignored)
2. **Production**: Use Kubernetes Secrets
3. **Secret Generation**: Use `scripts/generate-secure-secrets.sh`

### ⚠️ Exposed Secrets Response Plan

If secrets are accidentally exposed:

1. **Immediately** rotate all affected credentials
2. Remove secrets from git history using BFG Repo-Cleaner
3. Force push cleaned history
4. Regenerate all secrets using the provided script
5. Update Kubernetes secrets in all environments
6. Audit access logs for any unauthorized use

### 🛡️ Security Headers

The application implements comprehensive security headers:

- **Content Security Policy (CSP)**: Strict policy without `unsafe-inline` or `unsafe-eval`
- **HSTS**: Enforces HTTPS with preload
- **X-Frame-Options**: DENY (prevents clickjacking)
- **X-Content-Type-Options**: nosniff
- **Referrer-Policy**: strict-origin-when-cross-origin
- **Permissions-Policy**: Restricts browser features

### 🔒 Database Security

- **SSL/TLS Required**: All database connections must use SSL (`sslmode=require`)
- **Connection Pooling**: Managed with appropriate timeouts
- **Password Rotation**: Regular rotation policy enforced
- **Least Privilege**: Database user has minimal required permissions

### 🔑 Authentication & Authorization

- **Individual Staff Logins**: No shared accounts
- **Session Security**:
  - HTTPOnly cookies
  - Secure flag enabled
  - SameSite=Lax
  - 1-hour timeout for school environment
  - Sessions expire on browser close

### 📝 Compliance

- **FERPA**: Full audit logging of all student data access
- **FOIA**: Open records request compliance
- **Data Minimization**: Only collect necessary information
- **Encryption**: At-rest and in-transit

### 🚨 Security Checklist

Before deployment:

- [ ] All secrets removed from version control
- [ ] Secrets rotated after any exposure
- [ ] SSL enabled for database connections
- [ ] CSP headers configured without unsafe directives
- [ ] Admin credentials changed from defaults
- [ ] Audit logging enabled
- [ ] HTTPS enforced with HSTS
- [ ] Security headers validated
- [ ] Kubernetes RBAC configured
- [ ] Network policies in place

### 📊 Security Monitoring

1. **Failed Login Monitoring**: Track and alert on multiple failed attempts
2. **Audit Logs**: All student data access logged with timestamp and user
3. **Security Headers**: Regular validation using securityheaders.com
4. **Dependency Scanning**: Regular updates and vulnerability scanning
5. **SSL Certificate**: Monitor expiration and auto-renewal

### 🔄 Secret Rotation Schedule

- **Database Passwords**: Every 90 days
- **Django Secret Key**: Every 180 days
- **API Tokens**: Every 90 days
- **Admin Passwords**: Every 30 days

### 📞 Security Contacts

For security issues or questions:
- Report vulnerabilities privately via GitHub Security Advisory
- Never disclose security issues publicly before fixes are deployed

### 🛠️ Tools and Scripts

- **Generate Secrets**: `scripts/generate-secure-secrets.sh`
- **Security Scan**: `uv run bandit -r .`
- **Dependency Check**: `uv run safety check`
- **CSP Validation**: Check browser console for violations

### ⚡ Quick Security Fixes

If you discover exposed secrets:

```bash
# 1. Generate new secrets
./scripts/generate-secure-secrets.sh

# 2. Update Cloudflare token in the generated file
# Edit k8s/overlays/demo/secret.yaml

# 3. Apply to cluster
kubectl apply -f k8s/overlays/demo/secret.yaml

# 4. Restart pods to use new secrets
kubectl rollout restart deployment/web -n opendismissal-demo

# 5. Verify no secrets in git
git grep -i "password\|secret\|token" --untracked
```

---

**Remember**: Security is everyone's responsibility. When in doubt, ask for a security review.