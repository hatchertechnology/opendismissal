# OpenDismissal Kubernetes Deployment Runbook

## Pre-Deployment Checklist

### ✅ Prerequisites
- [ ] Container image built and pushed to `ghcr.io/hatchertechnology/opendismissal:latest`
- [ ] Digital Ocean Kubernetes (DOKS) cluster provisioned and accessible
- [ ] `kubectl` configured and connected to the DOKS cluster
- [ ] **CRITICAL**: cert-manager installed (see installation commands below)
- [ ] **CRITICAL**: nginx-ingress-controller installed (see installation commands below)
- [ ] Cloudflare API token obtained with Zone:Read + DNS:Edit permissions
- [ ] Domain `dismiss.hatchertechnology.com` managed by Cloudflare

### ⚠️ Install Required Cluster Components FIRST

**These MUST be installed before deploying OpenDismissal:**

```bash
# 1. Install cert-manager (for SSL certificates)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.2/cert-manager.yaml
kubectl wait --for=condition=available --timeout=60s deployment/cert-manager -n cert-manager

# 2. Install nginx-ingress-controller (for Digital Ocean)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.0/deploy/static/provider/do/deploy.yaml

# 3. Verify installations
kubectl get deployment -n cert-manager cert-manager
kubectl get deployment -n ingress-nginx ingress-nginx-controller
```

### ✅ Generate Secrets Properly

**Use the provided script to avoid DATABASE_URL encoding issues:**

```bash
# Generate secrets with proper URL encoding
./k8s/generate-secrets.sh k8s/overlays/demo/secret.yaml

# The script will:
# - Generate secure passwords
# - URL-encode special characters in DATABASE_URL
# - Prompt for admin email and Cloudflare token
```

### ✅ Required Manual Configuration
- [ ] Run generate-secrets.sh script to create properly formatted secrets
- [ ] Provide admin email when prompted
- [ ] Provide Cloudflare API token when prompted (or update later)
- [ ] If Cloudflare token skipped, update it in both:
  - `k8s/overlays/demo/external-dns-secret.yaml` (base64 encoded)
  - `k8s/overlays/demo/secret.yaml` (plain text)

## Deployment Commands

### Phase 1: Validate Configuration
```bash
# Test kustomize build
kubectl kustomize k8s/overlays/demo

# Validate manifests (expect cert-manager CRD warnings)
kubectl kustomize k8s/overlays/demo | kubectl apply --dry-run=client -f -
```

### Phase 2: Deploy Infrastructure and Application
```bash
# Deploy all resources with single command
kubectl apply -k k8s/overlays/demo

# Alternative: Deploy in phases for better control
# kubectl apply -k k8s/base
# kubectl apply -k k8s/overlays/demo
```

### Phase 3: Monitor Deployment Progress
```bash
# Watch all resources come up
watch kubectl get all -n opendismissal-demo

# Monitor pods specifically
kubectl get pods -n opendismissal-demo -w

# Check job completion
kubectl get jobs -n opendismissal-demo
```

### Phase 4: Verify Services Are Ready

#### Database (PostgreSQL)
```bash
kubectl logs -n opendismissal-demo statefulset/postgresql-demo
kubectl get pvc -n opendismissal-demo
```

#### Cache (Redis)
```bash
kubectl logs -n opendismissal-demo deployment/redis-demo
```

#### Web Application (Django)
```bash
kubectl logs -n opendismissal-demo deployment/django-demo
kubectl logs -n opendismissal-demo job/django-migrate-demo
```

### Phase 5: DNS and SSL Certificate Validation
```bash
# Check External DNS
kubectl logs -n opendismissal-demo deployment/external-dns-demo

# Check certificate issuers
kubectl get clusterissuers

# Check certificate status
kubectl get certificates -n opendismissal-demo
kubectl describe certificate django-tls-cert -n opendismissal-demo
```

### Phase 6: Application Setup Jobs
```bash
# Check migration job completion
kubectl logs -n opendismissal-demo job/django-migrate-demo

# Check superuser creation
kubectl logs -n opendismissal-demo job/create-superuser-demo

# Check demo data generation
kubectl logs -n opendismissal-demo job/generate-demo-data-demo
```

## Post-Deployment Verification

### Health Checks
```bash
# Test health endpoint via port-forward
kubectl port-forward -n opendismissal-demo service/django-service-demo 8080:80
curl http://localhost:8080/ht/

# Test DNS resolution
nslookup dismiss.hatchertechnology.com

# Test HTTPS access
curl -I https://dismiss.hatchertechnology.com/ht/
```

### Application Access
```bash
# Admin interface (use credentials from secret)
echo "Admin URL: https://dismiss.hatchertechnology.com/admin/"

# Get superuser credentials
kubectl get secret -n opendismissal-demo django-secrets-demo -o jsonpath='{.data.DJANGO_SUPERUSER_USERNAME}' | base64 -d
kubectl get secret -n opendismissal-demo django-secrets-demo -o jsonpath='{.data.DJANGO_SUPERUSER_PASSWORD}' | base64 -d
```

## Troubleshooting

### Common Issues

#### 1. PostgreSQL Not Starting
```bash
kubectl describe statefulset postgresql-demo -n opendismissal-demo
kubectl logs postgresql-demo-0 -n opendismissal-demo
# Check PVC: kubectl get pvc -n opendismissal-demo
```

#### 2. Django Migration Failures
```bash
kubectl describe job django-migrate-demo -n opendismissal-demo
kubectl logs job/django-migrate-demo -n opendismissal-demo
# Re-run if needed: kubectl delete job django-migrate-demo -n opendismissal-demo && kubectl apply -k k8s/overlays/demo
```

#### 3. External DNS Issues
```bash
kubectl logs deployment/external-dns-demo -n opendismissal-demo
# Check Cloudflare token: kubectl get secret external-dns-secret-demo -n opendismissal-demo -o yaml
```

#### 4. SSL Certificate Issues
```bash
kubectl describe certificate django-tls-cert -n opendismissal-demo
kubectl get challenges -n opendismissal-demo
# Check cert-manager logs: kubectl logs -n cert-manager deployment/cert-manager
```

#### 5. Service Connection Issues
```bash
kubectl get endpoints -n opendismissal-demo
kubectl describe service django-service-demo -n opendismissal-demo
```

### Resource Status Commands
```bash
# Overall cluster status
kubectl get all -n opendismissal-demo

# Storage status
kubectl get pvc,pv -n opendismissal-demo

# Network status
kubectl get ingress,services -n opendismissal-demo

# Security status
kubectl get secrets,configmaps -n opendismissal-demo

# Jobs and task status
kubectl get jobs -n opendismissal-demo
```

## Rollback Procedure

### Emergency Rollback
```bash
# Scale down web deployment
kubectl scale deployment django-demo --replicas=0 -n opendismissal-demo

# Delete all resources (preserves PVC data)
kubectl delete -k k8s/overlays/demo --ignore-not-found

# Re-apply previous working configuration
kubectl apply -k k8s/overlays/demo
```

### Partial Rollback (Web App Only)
```bash
kubectl rollout undo deployment/django-demo -n opendismissal-demo
kubectl rollout status deployment/django-demo -n opendismissal-demo
```

## Security Notes

### Secrets Management
- Never commit actual secrets to version control
- Rotate secrets regularly, especially the Django SECRET_KEY
- Use strong passwords for the PostgreSQL database
- Limit Cloudflare API token permissions to minimum required

### Access Control
- Default superuser credentials should be changed immediately after first login
- Consider enabling 2FA for admin accounts in production
- Regularly audit admin user access

## Scaling Notes

### Horizontal Scaling
```bash
# Scale Django application
kubectl scale deployment django-demo --replicas=5 -n opendismissal-demo

# Monitor resource usage
kubectl top pods -n opendismissal-demo
```

### Resource Limits
Current resource limits per component:
- **Django**: 256Mi-512Mi RAM, 200m-500m CPU
- **PostgreSQL**: 256Mi-512Mi RAM, 200m-500m CPU  
- **Redis**: 128Mi-256Mi RAM, 100m-200m CPU
- **External DNS**: 64Mi-128Mi RAM, 50m-100m CPU

## Monitoring and Logs

### Centralized Logging
```bash
# Stream all application logs
kubectl logs -f -l app.kubernetes.io/part-of=opendismissal-demo -n opendismissal-demo

# Application-specific logs
kubectl logs -f deployment/django-demo -n opendismissal-demo
kubectl logs -f statefulset/postgresql-demo -n opendismissal-demo
kubectl logs -f deployment/redis-demo -n opendismissal-demo
```

### Metrics and Health
```bash
# External DNS metrics
kubectl port-forward -n opendismissal-demo service/external-dns-demo 7979:7979
curl http://localhost:7979/metrics
```

## Success Criteria

Deployment is successful when:
- [ ] All pods are Running (0/X Ready status resolved)
- [ ] All jobs are Completed
- [ ] DNS resolves to correct IP: `nslookup dismiss.hatchertechnology.com`
- [ ] HTTPS certificate is valid: `curl -I https://dismiss.hatchertechnology.com/ht/`
- [ ] Health check returns 200: `/ht/` endpoint accessible
- [ ] Admin interface accessible: `/admin/` with valid login
- [ ] Database migrations completed successfully
- [ ] Demo data loaded (if applicable)

## Expected Deployment Time

- **Infrastructure**: 2-3 minutes
- **Database initialization**: 1-2 minutes  
- **Application deployment**: 2-3 minutes
- **SSL certificate provisioning**: 2-5 minutes
- **DNS propagation**: 1-10 minutes (varies by location)

**Total expected time**: 8-23 minutes for complete deployment and DNS propagation.