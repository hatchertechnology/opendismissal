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

Service dependencies should be managed through:
- `dependsOn` in Kustomize
- Init containers for database readiness
- Proper service discovery via DNS

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

This structure ensures maintainable, scalable Kubernetes deployments that integrate seamlessly with OpenDismissal's proven containerization approach.



IMPORTANT: Pause and wait for me to let you know I've read the overview and/or provide feedback before you create the file

If it is a small file show its contents, for larger files, show any important lines. 