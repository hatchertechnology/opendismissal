# DOKS Terraform Demo Cluster Implementation Plan
**Author:** Marcus Thompson  
**Date:** August 6, 2025  
**Status:** Ready for Implementation  
**Scope:** DigitalOcean Kubernetes Service cluster provisioning via Terraform

## Executive Summary

This plan outlines the implementation of a minimal DigitalOcean Kubernetes Service (DOKS) cluster using Terraform for OpenDismissal demo deployment. The approach prioritizes simplicity while addressing critical infrastructure best practices identified through expert review.

**Key Decisions:**
- Local Terraform state for demo simplicity (migration path available)
- Data source lookup for existing VPC integration
- WebSocket support deferred to future implementation
- Database strategy handled outside Terraform scope
- Minimal node pool configuration for cost optimization

## Background & Context

### Application Overview
OpenDismissal is a Django-based school dismissal management system requiring:
- Container orchestration (K8s) for scalability
- PostgreSQL and Redis backends
- Future WebSocket support for real-time features
- FERPA compliance and audit logging

### Infrastructure Requirements
- Existing VPC: `atl1-vpc-01` in ATL1 region
- Node specs: 4GB (s-2vcpu-4gb), 2-6 auto-scaling
- Integration with proven container: `ghcr.io/hatchertechnology/opendismissal:latest`
- Health check endpoint: `/ht/`

### Expert Review Findings
Four specialists (2 deployment engineers, 2 Terraform experts) identified:
- **Critical:** Missing remote state management (addressed with local state for demo)
- **Critical:** Hardcoded VPC UUID (resolved with data source pattern)
- **Important:** WebSocket load balancer compatibility (deferred)
- **Moderate:** Database persistence concerns (out of scope)

## Technical Implementation

### Terraform File Structure
```
tf/
└── environments/
    └── demo/
        ├── main.tf              # Primary resources
        ├── variables.tf         # Input parameters
        ├── terraform.tfvars     # Demo-specific values
        ├── versions.tf          # Provider constraints
        └── outputs.tf           # Connection information
```

### Core Resources

#### 1. VPC Integration
```hcl
data "digitalocean_vpc" "existing" {
  name = var.vpc_name
}
```
- Lookup existing VPC by name for portability
- Avoid hardcoded UUIDs per expert recommendation
- Variable: `vpc_name = "atl1-vpc-01"`

#### 2. DOKS Cluster
```hcl
resource "digitalocean_kubernetes_cluster" "demo" {
  name    = var.cluster_name
  region  = var.region
  version = var.kubernetes_version
  vpc_uuid = data.digitalocean_vpc.existing.id

  node_pool {
    name       = "${var.cluster_name}-pool"
    size       = var.node_size
    auto_scale = true
    min_nodes  = var.min_nodes
    max_nodes  = var.max_nodes
  }

  tags = var.cluster_tags
}
```

#### 3. Key Variables
- `cluster_name = "opendismissal-demo"`
- `region = "atl1"`
- `node_size = "s-2vcpu-4gb"`
- `min_nodes = 2`
- `max_nodes = 6`
- `kubernetes_version = "latest"` (or specific stable version)

### Configuration Files

#### terraform.tfvars
```hcl
cluster_name       = "opendismissal-demo"
region            = "atl1"
vpc_name          = "atl1-vpc-01"
node_size         = "s-2vcpu-4gb"
min_nodes         = 2
max_nodes         = 6
kubernetes_version = "1.28.2-do.0"

cluster_tags = ["demo", "opendismissal", "education"]
```

#### outputs.tf
```hcl
output "cluster_id" {
  description = "ID of the Kubernetes cluster"
  value       = digitalocean_kubernetes_cluster.demo.id
}

output "cluster_endpoint" {
  description = "Endpoint for Kubernetes API server"
  value       = digitalocean_kubernetes_cluster.demo.endpoint
}

output "kubeconfig" {
  description = "Kubeconfig for cluster access"
  value       = digitalocean_kubernetes_cluster.demo.kube_config.0.raw_config
  sensitive   = true
}
```

## Implementation Steps

### Phase 1: Terraform Setup
1. **Initialize environment:**
   ```bash
   cd tf/environments/demo
   terraform init
   terraform validate
   ```

2. **Plan deployment:**
   ```bash
   terraform plan -var-file="terraform.tfvars"
   ```

3. **Apply infrastructure:**
   ```bash
   terraform apply -var-file="terraform.tfvars"
   ```

### Phase 2: Cluster Access
1. **Configure kubectl:**
   ```bash
   terraform output -raw kubeconfig > ~/.kube/config-opendismissal-demo
   export KUBECONFIG=~/.kube/config-opendismissal-demo
   ```

2. **Verify cluster:**
   ```bash
   kubectl get nodes
   kubectl get namespaces
   ```

### Phase 3: Application Deployment (Out of Scope)
- Apply K8s manifests from `/k8s/overlays/demo/`
- Verify health checks on `/ht/` endpoint
- Configure ingress for external access

## Risk Assessment & Mitigation

### High Risks
1. **Local State Management**
   - **Risk:** State corruption, team collaboration issues
   - **Mitigation:** Document migration to remote state; limit demo to single operator
   - **Migration Path:** Use `terraform state` commands when ready

2. **VPC Dependency**
   - **Risk:** VPC deletion breaks cluster
   - **Mitigation:** Data source will fail fast if VPC missing; VPC is stable infrastructure

### Medium Risks
1. **Node Pool Scaling**
   - **Risk:** Cost overrun with max 6 nodes
   - **Mitigation:** Monitor usage; demo should stay at 2-3 nodes typically

2. **Kubernetes Version**
   - **Risk:** Version compatibility with existing container
   - **Mitigation:** Use stable/recent version; container uses standard K8s patterns

## Cost Estimation

**Monthly Demo Costs (ATL1 region):**
- 2x s-2vcpu-4gb nodes: ~$48/month ($24 each)
- Load balancer: ~$12/month
- **Total baseline:** ~$60/month
- **Max scaling (6 nodes):** ~$144/month

## Success Criteria

### Technical
- [ ] Cluster provisions successfully in existing VPC
- [ ] Node pool auto-scaling functions (2-6 nodes)
- [ ] kubectl access configured and verified
- [ ] Integration ready for K8s manifest deployment

### Operational  
- [ ] Terraform state management documented
- [ ] Cost monitoring baseline established
- [ ] Migration path to remote state documented
- [ ] Cleanup procedures defined

## Future Considerations

### Remote State Migration
When ready for team collaboration:
1. Create DigitalOcean Spaces bucket
2. Configure backend in `versions.tf`
3. Migrate using `terraform init -migrate-state`

### Production Readiness
For production deployment:
- Implement remote state backend
- Add monitoring and alerting
- Configure backup strategies
- Implement proper RBAC
- Add network security groups
- Enable audit logging

### WebSocket Support
When implementing real-time features:
- Research DO load balancer WebSocket compatibility
- Test connection upgrades with sample application
- Configure ingress annotations if required

## Implementation Notes

### Terraform Provider Versions
- DigitalOcean provider: `~> 2.34`
- Terraform core: `>= 1.0`

### Integration Points
- **Container Registry:** `ghcr.io/hatchertechnology/opendismissal:latest`
- **K8s Manifests:** `/k8s/overlays/demo/` (existing structure)
- **Health Checks:** `/ht/` endpoint
- **Port:** 8000 (container standard)

### Security Considerations
- Cluster uses private VPC networking
- Node-to-node encryption enabled by default
- RBAC follows K8s defaults
- No additional security groups required for demo

---

**Implementation Owner:** Infrastructure Team  
**Review Required:** Security team (for production promotion)  
**Estimated Implementation Time:** 2-4 hours  
**Dependencies:** DigitalOcean account access, existing VPC operational