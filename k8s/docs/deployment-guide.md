# OpenDismissal Kubernetes Deployment Guide

This guide explains how to deploy OpenDismissal using the new base + overlay structure with Kustomize.

## Prerequisites

- Container image built and pushed to `ghcr.io/hatchertechnology/opendismissal:latest`
- DOKS cluster with cert-manager and nginx-ingress installed
- Cloudflare API token with Zone:Read + DNS:Edit permissions
- All placeholder values replaced with actual credentials

## New Structure Overview

The k8s manifests are now organized using Kustomize base + overlay pattern:

```
k8s/
├── base/                          # Environment-agnostic manifests
│   ├── namespace.yaml
│   ├── postgres-deployment.yaml   # StatefulSet for PostgreSQL
│   ├── postgres-service.yaml
│   ├── web-deployment.yaml       # Django deployment
│   ├── web-service.yaml
│   └── kustomization.yaml
├── overlays/                     # Environment-specific customizations
│   └── demo/
│       ├── kustomization.yaml
│       ├── configmap.yaml        # Demo environment config
│       ├── secret.yaml           # Demo secrets (base64 encoded)
│       ├── ingress.yaml
│       ├── cert-manager-issuers.yaml
│       ├── external-dns-*.yaml
│       └── *-job.yaml             # Initialization jobs
└── docs/
    └── deployment-guide.md
```

## Deployment Commands

### Deploy Demo Environment

```bash
# Deploy all manifests for demo environment
kubectl apply -k k8s/overlays/demo

# Or build and apply separately
kubectl kustomize k8s/overlays/demo | kubectl apply -f -
```

### Validate Deployment

```bash
# Check all resources in demo namespace
kubectl get all -n opendismissal-demo

# Check jobs status
kubectl get jobs -n opendismissal-demo

# Check pod logs
kubectl logs -f deployment/django-demo -n opendismissal-demo
```

### Phase-by-Phase Deployment (if needed)

For controlled deployments, you can apply resources in phases:

```bash
# Phase 1: Infrastructure
kubectl apply -k k8s/base

# Phase 2: Demo configuration
kubectl apply -f k8s/overlays/demo/configmap.yaml
kubectl apply -f k8s/overlays/demo/secret.yaml

# Phase 3: Application
kubectl apply -f k8s/overlays/demo/migration-job.yaml
# Wait for migration to complete
kubectl apply -k k8s/overlays/demo
```

## Environment Differences

### Base Configuration
- Uses `opendismissal` namespace (gets patched by overlay)
- Environment-agnostic container configurations
- Standard resource requests/limits
- Basic health checks and security contexts

### Demo Overlay
- Patches namespace to `opendismissal-demo`
- Adds `-demo` suffix to resource names
- Includes demo-specific:
  - Domain: `dismiss.hatchertechnology.com`
  - Let's Encrypt staging certificates
  - External-DNS for Cloudflare
  - Demo data generation jobs

## Adding New Environments

To create a new environment (e.g., production):

1. Create `k8s/overlays/production/` directory
2. Create `kustomization.yaml` referencing base
3. Add environment-specific configurations
4. Update namespace patches and resource names

Example production kustomization:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: opendismissal-prod

resources:
- ../../base
- configmap.yaml
- secret.yaml
- ingress.yaml

nameSuffix: "-prod"

commonLabels:
  app.kubernetes.io/part-of: opendismissal-prod
  environment: production

patches:
- target:
    kind: Namespace
    name: opendismissal
  patch: |-
    - op: replace
      path: /metadata/name
      value: opendismissal-prod
    - op: add
      path: /metadata/labels/environment
      value: production
```

## Troubleshooting

### Common Issues

1. **Namespace patch errors**: Ensure the target namespace name matches base
2. **Resource naming conflicts**: Use nameSuffix in overlays
3. **ConfigMap/Secret references**: Names get suffixed, update references accordingly

### Validation Commands

```bash
# Test kustomize build without applying
kubectl kustomize k8s/overlays/demo

# Check resource naming
kubectl kustomize k8s/overlays/demo | grep "name:"

# Validate against cluster (dry-run)
kubectl kustomize k8s/overlays/demo | kubectl apply --dry-run=client -f -
```

## Benefits of New Structure

1. **DRY Principle**: Base manifests shared across environments
2. **GitOps Ready**: Clean separation for ArgoCD deployment
3. **Environment Promotion**: Easy staging → production workflow
4. **Maintenance**: Single source of truth for core configuration
5. **Scalability**: Add new environments without duplicating base config

## Migration from Old Structure

The old flat structure files remain in the root `k8s/` directory for reference but should not be used for deployments. Use the new overlay structure:

```bash
# Old way (deprecated)
kubectl apply -f k8s/django-deployment.yaml
kubectl apply -f k8s/postgresql-statefulset.yaml

# New way
kubectl apply -k k8s/overlays/demo
```