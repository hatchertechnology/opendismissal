# Kubernetes Deployment Standards

This document outlines the standards and structure for Kubernetes manifests in the OpenDismissal project.

## Folder Structure

The k8s folder follows standard Kubernetes conventions with a base + overlays pattern:

```
k8s/
├── base/                          # Base manifests (environment-agnostic)
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml               # Template/example only
│   ├── postgres-deployment.yaml
│   ├── postgres-service.yaml
│   ├── postgres-pvc.yaml
│   ├── redis-deployment.yaml
│   ├── redis-service.yaml
│   ├── web-deployment.yaml
│   ├── web-service.yaml
│   └── web-ingress.yaml
├── overlays/                     # Environment-specific customizations
│   ├── demo/
│   │   ├── kustomization.yaml
│   │   ├── demo-configmap.yaml
│   │   └── demo-ingress-patch.yaml
│   ├── staging/
│   └── production/
└── docs/
    ├── deployment-guide.md
    ├── secrets-setup.md
    └── troubleshooting.md
```

## Standards and Conventions

### File Organization
- **Single manifest per file** - Each YAML file contains only one Kubernetes resource
- **Resource type in filename** - Files are named with the pattern `<component>-<resource-type>.yaml`
- **Logical grouping** - Components are grouped by application tier (postgres, redis, web)

### Naming Conventions
- Use lowercase with hyphens for resource names
- Prefix with `opendismissal-` for uniqueness in shared clusters
- Include environment suffix for overlays (e.g., `opendismissal-web-demo`)

### Base Manifests
Base manifests in `base/` should be:
- Environment-agnostic
- Use placeholder values that can be overridden
- Include proper labels and selectors
- Define resource requests and limits
- Include health checks and readiness probes

### Environment Overlays
Each environment overlay should:
- Use Kustomize for configuration management
- Override only necessary values from base
- Include environment-specific secrets and configs
- Set appropriate resource limits for the environment

### Container Integration
All manifests should reference the proven container image:
- **Image**: `ghcr.io/hatchertechnology/opendismissal:latest`
- **Health Check**: Use `/ht/` endpoint for liveness/readiness probes
- **Port**: Container exposes port 8000
- **User**: Runs as non-root user (UID 1000)

### Dependencies
The application stack requires:
1. **PostgreSQL 16** - Primary database
2. **Redis 7** - Session storage and message broker
3. **Django Web App** - Main application with WebSocket support
4. **External DNS with Cloudflare** - Automatic DNS record management

Service dependencies should be managed through:
- `dependsOn` in Kustomize
- Init containers for database readiness
- Proper service discovery via DNS

### DNS Management
**IMPORTANT**: This project uses **Cloudflare** as the DNS provider for External DNS:
- Complete setup guide: `docs/k8-external-dns-cloudflare.md`
- Cloudflare API tokens are required for DNS record automation
- External DNS automatically creates and manages DNS records for Kubernetes services and ingresses
- Use the Cloudflare provider configuration, not Digital Ocean DNS

### Security Considerations
- Never commit actual secrets to git
- Use Kubernetes secrets for sensitive data
- Reference secrets template files for structure
- Apply least privilege principles
- Use security contexts and pod security standards

### Deployment Process
For demo deployments:
1. Apply base manifests with demo overlay: `kubectl apply -k overlays/demo`
2. Verify health checks pass
3. Access via configured ingress or port-forward

For production deployments:
1. Ensure secrets are properly configured
2. Apply production overlay with appropriate resource limits
3. Monitor deployment rollout
4. Verify all health checks and connectivity

### GitOps Integration
This structure is designed to work with:
- **ArgoCD** for automated deployments
- **Kustomize** for configuration management
- **Git-based workflows** for change management
- **Environment promotion** through overlays

## Key Integration Points

### Health Checks
All deployments should use the Django health check endpoint:
```yaml
livenessProbe:
  httpGet:
    path: /ht/
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
```

### Environment Variables
Critical environment variables from docker-compose.yml:
- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Redis connection
- `SECRET_KEY` - Django secret key
- `ALLOWED_HOSTS` - Comma-separated hostnames
- `DEBUG` - Should be False in production

### Volume Mounts
- `/app/logs` - Application logs (should be mounted or use logging sidecar)
- `/app/media` - User uploads (needs persistent volume)
- `/app/staticfiles` - Static assets (can be ephemeral or CDN)

## Development Workflow

When adding new Kubernetes resources:
1. Create in `base/` directory first
2. Use single manifest per file
3. Follow naming conventions
4. Test with demo overlay
5. Add documentation if complex
6. Consider production implications

## Critical Deployment Prerequisites

### Required Cluster Components
Before deploying OpenDismissal, ensure these components are installed in your cluster:

1. **cert-manager** (REQUIRED for SSL certificates)
   ```bash
   kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.2/cert-manager.yaml
   kubectl wait --for=condition=available --timeout=60s deployment/cert-manager -n cert-manager
   ```

2. **nginx-ingress-controller** (REQUIRED for traffic routing)
   ```bash
   # For Digital Ocean clusters:
   kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.0/deploy/static/provider/do/deploy.yaml
   ```

3. **Verify prerequisites**:
   ```bash
   kubectl get deployment -n cert-manager cert-manager
   kubectl get deployment -n ingress-nginx ingress-nginx-controller
   ```

### Secret Generation Best Practices

**CRITICAL**: Database passwords with special characters MUST be URL-encoded in the DATABASE_URL string.

Use the provided secret generation script to avoid encoding issues:
```bash
./k8s/generate-secrets.sh k8s/overlays/demo/secret.yaml
```

The script automatically:
- Generates cryptographically secure passwords
- URL-encodes passwords for DATABASE_URL
- Creates properly formatted secret manifests
- Prompts for required user inputs (email, Cloudflare token)

### Common Deployment Gotchas

1. **DATABASE_URL Encoding Issues**
   - **Problem**: PostgreSQL passwords with special characters (/, =, ?, &) break DATABASE_URL parsing
   - **Solution**: Always URL-encode passwords in DATABASE_URL using the generate-secrets.sh script
   - **Example**: `password/with=special` becomes `password%2Fwith%3Dspecial`

2. **Cert-Manager CRD Warnings**
   - **Problem**: First deployment shows "no matches for kind ClusterIssuer" warnings
   - **Solution**: Install cert-manager before deployment, then apply cert-manager-issuers.yaml separately
   - **Note**: These warnings are harmless if cert-manager is installed afterward

3. **Ingress Controller Missing**
   - **Problem**: Ingress resources created but no external IP assigned
   - **Solution**: Install nginx-ingress-controller for your cloud provider
   - **Digital Ocean**: Use the DO-specific nginx-ingress manifest

4. **External DNS Cloudflare Token**
   - **Problem**: External DNS fails with authentication errors
   - **Solution**: Ensure Cloudflare API token has Zone:Read and DNS:Edit permissions
   - **Token Location**: Update in both external-dns-secret.yaml and secret.yaml

5. **Pod Init Container Loops**
   - **Problem**: Django pods stuck in Init:0/1 waiting for database
   - **Solution**: Check PostgreSQL pod logs and ensure it's running successfully
   - **Common Cause**: PVC provisioning issues or resource constraints

### Deployment Order and Timing

The proper deployment sequence is handled automatically by Kustomize, but understanding the order helps with troubleshooting:

1. **Infrastructure** (1-2 minutes)
   - Namespace creation
   - RBAC resources
   - ConfigMaps and Secrets

2. **Data Layer** (2-3 minutes)
   - PostgreSQL StatefulSet (waits for PVC)
   - Redis Deployment

3. **Application Layer** (2-3 minutes)
   - Django Deployment (waits for database via init container)
   - Migration Job (waits for database)
   - External DNS Deployment

4. **Post-Deployment Jobs** (1-2 minutes)
   - Superuser creation (after migrations)
   - Demo data generation (after migrations)

5. **Ingress and SSL** (3-15 minutes)
   - Ingress resource creation
   - SSL certificate provisioning via Let's Encrypt
   - DNS propagation (varies by location)

### Troubleshooting Quick Reference

| Issue | Check Command | Common Fix |
|-------|--------------|------------|
| Pods not starting | `kubectl describe pod <pod-name> -n opendismissal-demo` | Check events section for errors |
| Database connection failed | `kubectl logs <django-pod> -n opendismissal-demo` | Verify DATABASE_URL encoding |
| No external IP | `kubectl get ingress -n opendismissal-demo` | Install nginx-ingress-controller |
| SSL cert pending | `kubectl get certificate -n opendismissal-demo` | Check cert-manager logs |
| DNS not resolving | `kubectl logs deployment/external-dns-demo -n opendismissal-demo` | Verify Cloudflare token |

This structure ensures maintainable, scalable Kubernetes deployments that integrate seamlessly with OpenDismissal's proven containerization approach.



IMPORTANT: Pause and wait for me to let you know I've read the overview and/or provide feedback before you create the file

If it is a small file show its contents, for larger files, show any important lines. 