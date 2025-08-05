# OpenDismissal DigitalOcean Kubernetes Deployment Plan
**Author:** Claude (Senior Platform Engineer)  
**Date:** January 2025  
**Status:** DOKS-Optimized Planning Phase  
**Target Platform:** DigitalOcean Managed Kubernetes Service (DOKS)  
**Production FQDN:** dismiss.hatchertechnology.com

## Executive Summary

This document outlines a comprehensive deployment strategy for OpenDismissal on DigitalOcean Managed Kubernetes Service (DOKS). The deployment leverages DOKS-native features including DO Block Storage, Load Balancers, Container Registry (DOCR), and optionally managed database services for optimal performance and cost efficiency.

## DOKS Platform Analysis

### DigitalOcean Kubernetes Service Features
- **Managed Control Plane:** No control plane costs, automatic updates
- **Cilium CNI:** Advanced networking with eBPF (already running in cluster)
- **Native Load Balancer Integration:** Automatic DO Load Balancer provisioning
- **Block Storage Integration:** High-performance SSD storage classes
- **Container Registry (DOCR):** Integrated, cost-effective image storage
- **Monitoring Integration:** Native DO monitoring and alerting
- **Auto-scaling:** Horizontal and vertical pod autoscaling support

### Current Cluster Status
Based on cluster inspection, the environment includes:
- Cilium networking (pod: `cilium-crx67`)
- CoreDNS for service discovery
- DO-specific agents (node agent, CSI driver)
- Network observability (Hubble UI/Relay)

## Revised Architecture for DOKS

### Hybrid Architecture Decision Matrix

| Component | In-Cluster | DO Managed Service | Recommendation | Rationale |
|-----------|------------|-------------------|----------------|-----------|
| **PostgreSQL** | ✓ StatefulSet | ✓ DO Managed DB | **DO Managed DB** | Better backup, maintenance, scaling |
| **Redis** | ✓ Deployment | ✓ DO Managed Redis | **In-Cluster** | Session data locality, cost optimization |
| **Application** | ✓ Deployment | N/A | **In-Cluster** | Custom Django app with WebSockets |
| **Load Balancer** | nginx ingress | DO Load Balancer | **DO Load Balancer** | Native integration, SSL termination |

### Updated Resource Topology
```
┌─────────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   DO Load Balancer  │    │   DOKS Cluster   │    │   DO Managed        │
│   - SSL Termination │───▶│   - Django Pods  │───▶│   PostgreSQL        │
│   - Health Checks   │    │   - Redis Pod    │    │   - Automated       │
│   - Static Files    │    │   - 2-3 replicas │    │     Backups         │
└─────────────────────┘    └──────────────────┘    │   - Read Replicas   │
                                   │                 └─────────────────────┘
                                   ▼
                            ┌─────────────────┐
                            │   DO Block      │
                            │   Storage       │
                            │   - Audit Logs  │
                            │   - Media Files │
                            └─────────────────┘
```

## DOKS-Specific Deployment Components

### 1. Storage Strategy (DO Block Storage)

**Storage Classes Available:**
```yaml
# High-performance SSD storage (default)
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: do-block-storage
provisioner: dobs.csi.digitalocean.com
parameters:
  type: pd-ssd
allowVolumeExpansion: true
reclaimPolicy: Delete

# Retain policy for critical data
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: do-block-storage-retain
provisioner: dobs.csi.digitalocean.com
parameters:
  type: pd-ssd
allowVolumeExpansion: true
reclaimPolicy: Retain
```

**Volume Specifications:**
- **Audit Logs:** 10GB `do-block-storage-retain` (critical data)
- **Media Files:** 20GB `do-block-storage` (expandable)
- **Redis Persistence:** 5GB `do-block-storage`

### 2. DO Managed PostgreSQL Integration

**Recommended Configuration:**
- **Plan:** Basic ($15/month) or Professional ($60/month)
- **Size:** 1GB RAM, 1 vCPU (Basic) or 2GB RAM, 1 vCPU (Professional)
- **Storage:** 25GB SSD (auto-scaling available)
- **Features:**
  - Automated daily backups (7-day retention)
  - Point-in-time recovery
  - Connection pooling (PgBouncer)
  - Read replicas (Professional plan)
  - Automated maintenance windows

**Connection Configuration:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: postgres-credentials
type: Opaque
stringData:
  database-url: "postgresql://username:password@db-cluster-do-user-123456-0.b.db.ondigitalocean.com:25060/opendismissal?sslmode=require"
```

### 3. DigitalOcean Load Balancer Service

**Service Configuration for dismiss.hatchertechnology.com:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: opendismissal-loadbalancer
  annotations:
    service.beta.kubernetes.io/do-loadbalancer-protocol: "http"
    service.beta.kubernetes.io/do-loadbalancer-algorithm: "round_robin"
    service.beta.kubernetes.io/do-loadbalancer-size-slug: "lb-small"
    service.beta.kubernetes.io/do-loadbalancer-enable-proxy-protocol: "true"
    service.beta.kubernetes.io/do-loadbalancer-hostname: "dismiss.hatchertechnology.com"
    service.beta.kubernetes.io/do-loadbalancer-certificate-id: "hatcher-tech-cert-id"
    service.beta.kubernetes.io/do-loadbalancer-tls-ports: "443"
    service.beta.kubernetes.io/do-loadbalancer-redirect-http-to-https: "true"
    service.beta.kubernetes.io/do-loadbalancer-disable-lets-encrypt-dns-records: "false"
spec:
  type: LoadBalancer
  selector:
    app: opendismissal
  ports:
    - name: http
      port: 80
      targetPort: 8000
    - name: https
      port: 443
      targetPort: 8000
```

**Load Balancer Features:**
- **SSL Termination:** Let's Encrypt certificate for dismiss.hatchertechnology.com
- **Health Checks:** Automated health monitoring
- **Automatic HTTPS Redirect:** HTTP traffic redirected to HTTPS
- **DDoS Protection:** Built-in protection included
- **Sticky Sessions:** Support for WebSocket connections
- **Domain Integration:** Native support for hatchertechnology.com domain

### 4. Container Registry Strategy (DOCR)

**DOCR Integration:**
```yaml
# Image pull secret for DOCR
apiVersion: v1
kind: Secret
metadata:
  name: docr-secret
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: <base64-encoded-docker-config>

---
# Deployment with DOCR image
apiVersion: apps/v1
kind: Deployment
metadata:
  name: opendismissal
spec:
  template:
    spec:
      imagePullSecrets:
        - name: docr-secret
      containers:
        - name: django
          image: registry.digitalocean.com/your-registry/opendismissal:latest
```

**DOCR Benefits:**
- **Cost Effective:** $5/month for 5GB storage
- **Private Registry:** Secure image storage
- **Regional Mirrors:** Faster image pulls
- **Integration:** Native DOKS integration
- **Vulnerability Scanning:** Built-in security scanning

### 5. Enhanced Application Deployment

**Optimized Deployment Configuration:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: opendismissal
  namespace: opendismissal
spec:
  replicas: 2
  selector:
    matchLabels:
      app: opendismissal
  template:
    metadata:
      labels:
        app: opendismissal
    spec:
      imagePullSecrets:
        - name: docr-secret
      containers:
        - name: django
          image: registry.digitalocean.com/your-registry/opendismissal:latest
          ports:
            - containerPort: 8000
              name: http
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: postgres-credentials
                  key: database-url
            - name: REDIS_URL
              value: "redis://redis-service:6379/0"
            - name: ALLOWED_HOSTS
              value: "dismiss.hatchertechnology.com,localhost,127.0.0.1"
            - name: DEBUG
              value: "false"
            - name: TIME_ZONE
              value: "America/New_York"
          resources:
            requests:
              memory: "256Mi"
              cpu: "200m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          volumeMounts:
            - name: audit-logs
              mountPath: /app/logs
            - name: media-files
              mountPath: /app/media
          livenessProbe:
            httpGet:
              path: /health/
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health/ready/
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
      volumes:
        - name: audit-logs
          persistentVolumeClaim:
            claimName: audit-logs-pvc
        - name: media-files
          persistentVolumeClaim:
            claimName: media-files-pvc
```

### 6. Redis Deployment (In-Cluster)

**Redis with DO Block Storage:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: opendismissal
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
          resources:
            requests:
              memory: "64Mi"
              cpu: "50m"
            limits:
              memory: "256Mi"
              cpu: "200m"
          volumeMounts:
            - name: redis-data
              mountPath: /data
          command:
            - redis-server
            - --appendonly
            - "yes"
            - --requirepass
            - "$(REDIS_PASSWORD)"
          env:
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: redis-secret
                  key: password
      volumes:
        - name: redis-data
          persistentVolumeClaim:
            claimName: redis-pvc
```

## Networking and Security (Cilium-Optimized)

### Network Policies
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: opendismissal-netpol
  namespace: opendismissal
spec:
  podSelector:
    matchLabels:
      app: opendismissal
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector: {}  # Same namespace
      ports:
        - protocol: TCP
          port: 8000
  egress:
    - to: []  # Allow all egress (for external DB)
      ports:
        - protocol: TCP
          port: 5432  # PostgreSQL
        - protocol: TCP
          port: 25060  # DO Managed PostgreSQL
    - to:
        - podSelector:
            matchLabels:
              app: redis
      ports:
        - protocol: TCP
          port: 6379
```

### Pod Security Standards
```yaml
apiVersion: v1
kind: Pod
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 1000
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: django
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop:
            - ALL
```

## DOKS-Optimized Monitoring and Observability

### DigitalOcean Monitoring Integration
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: monitoring-config
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
    scrape_configs:
      - job_name: 'opendismissal'
        static_configs:
          - targets: ['opendismissal-service:8000']
        metrics_path: '/metrics'
      - job_name: 'redis'
        static_configs:
          - targets: ['redis-service:6379']
```

**Monitoring Stack:**
- **DO Monitoring:** Native infrastructure metrics
- **Prometheus:** Application metrics scraping
- **Custom Metrics:** Django-prometheus integration
- **Log Aggregation:** Fluentd to DO monitoring

### Alerting Configuration
```yaml
# Alert for high pod memory usage
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: opendismissal-alerts
spec:
  groups:
    - name: opendismissal
      rules:
        - alert: HighMemoryUsage
          expr: container_memory_usage_bytes{pod=~"opendismissal-.*"} / container_spec_memory_limit_bytes > 0.8
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "High memory usage in OpenDismissal pod"
```

## Cost Optimization Strategy

### DOKS Pricing Breakdown (Monthly)
| Component | Configuration | Cost |
|-----------|---------------|------|
| **DOKS Control Plane** | Managed | $0 (Free) |
| **Worker Nodes** | 2x Basic Droplets (2GB/1vCPU) | $24 |
| **DO Load Balancer** | Small (1GB) | $12 |
| **DO Managed PostgreSQL** | Basic (1GB/1vCPU) | $15 |
| **Block Storage** | 35GB SSD | $3.50 |
| **DOCR** | 5GB registry | $5 |
| **Bandwidth** | 1TB included | $0 |
| **Total Estimated** | | **$59.50/month** |

### Cost Optimization Recommendations
1. **Start Small:** Use Basic PostgreSQL plan, scale as needed
2. **Efficient Images:** Multi-stage Docker builds to reduce registry costs
3. **Resource Limits:** Prevent resource waste with proper limits
4. **Autoscaling:** Scale down during off-hours
5. **Reserved Capacity:** Consider reserved instances for predictable workloads

## Performance Optimizations

### DOKS-Specific Tuning
```yaml
# HPA with DOKS optimization
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: opendismissal-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: opendismissal
  minReplicas: 2
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 50
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Percent
          value: 100
          periodSeconds: 60
```

### Database Connection Optimization
```python
# Django settings for DO Managed PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'opendismissal',
        'USER': 'doadmin',
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': 'db-cluster-do-user-123456-0.b.db.ondigitalocean.com',
        'PORT': '25060',
        'OPTIONS': {
            'sslmode': 'require',
            'connect_timeout': 10,
            'options': '-c default_transaction_isolation=read_committed'
        },
        'CONN_MAX_AGE': 600,  # Connection pooling
    }
}
```

## Backup and Disaster Recovery

### DO Managed Database Backups
- **Automatic Daily Backups:** 7-day retention (Basic), 30-day (Professional)
- **Point-in-Time Recovery:** Professional plan only
- **Cross-Region Backups:** Available in Professional plan

### Application Data Backup
```yaml
# Backup job for audit logs
apiVersion: batch/v1
kind: CronJob
metadata:
  name: audit-log-backup
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: backup
              image: digitalocean/doctl:latest
              command:
                - /bin/sh
                - -c
                - |
                  # Backup audit logs to DO Spaces
                  tar -czf /tmp/audit-logs-$(date +%Y%m%d).tar.gz /app/logs/
                  doctl spaces object put audit-backups /tmp/audit-logs-$(date +%Y%m%d).tar.gz
              volumeMounts:
                - name: audit-logs
                  mountPath: /app/logs
                  readOnly: true
              env:
                - name: DIGITALOCEAN_ACCESS_TOKEN
                  valueFrom:
                    secretKeyRef:
                      name: do-spaces-secret
                      key: access-token
          volumes:
            - name: audit-logs
              persistentVolumeClaim:
                claimName: audit-logs-pvc
          restartPolicy: OnFailure
```

## DNS and Domain Configuration

### DNS Setup Requirements
1. **A Record Configuration:**
   - Point `dismiss.hatchertechnology.com` to DO Load Balancer IP
   - TTL: 300 seconds for initial deployment flexibility

2. **SSL Certificate Management:**
   ```bash
   # Create SSL certificate in DO Console or via API
   doctl compute certificate create \
     --name hatcher-tech-dismiss \
     --dns-names dismiss.hatchertechnology.com \
     --type lets_encrypt
   ```

3. **Domain Validation:**
   - Verify domain ownership through DNS TXT record
   - Automatic Let's Encrypt certificate provisioning
   - Certificate auto-renewal enabled

### ConfigMap for Domain-Specific Settings
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: domain-config
  namespace: opendismissal
data:
  SITE_DOMAIN: "dismiss.hatchertechnology.com"
  SITE_URL: "https://dismiss.hatchertechnology.com"
  ALLOWED_HOSTS: "dismiss.hatchertechnology.com,localhost,127.0.0.1"
  CORS_ALLOWED_ORIGINS: "https://dismiss.hatchertechnology.com"
  CSRF_TRUSTED_ORIGINS: "https://dismiss.hatchertechnology.com"
```

## Implementation Timeline (DOKS-Optimized)

### Phase 1: Foundation Setup (Week 1)
- [x] DOKS cluster analysis and validation
- [ ] Domain DNS configuration for dismiss.hatchertechnology.com
- [ ] SSL certificate provisioning for hatchertechnology.com domain
- [ ] DO Managed PostgreSQL provisioning
- [ ] DOCR setup and Docker image optimization
- [ ] Basic application deployment with DO Load Balancer

### Phase 2: Storage and Persistence (Week 2)
- [ ] DO Block Storage PVC configuration
- [ ] Redis deployment with persistence
- [ ] Audit logging to persistent volumes
- [ ] Database migration and data seeding

### Phase 3: Security and Networking (Week 3)
- [ ] Network policies with Cilium optimization
- [ ] SSL certificate configuration on Load Balancer
- [ ] Secret management and RBAC setup
- [ ] Security scanning and compliance validation

### Phase 4: Monitoring and Scaling (Week 4)
- [ ] DO Monitoring integration
- [ ] Prometheus and custom metrics setup
- [ ] HPA configuration and testing
- [ ] Performance testing and optimization

### Phase 5: Production Deployment (Week 5)
- [ ] Production environment setup
- [ ] Backup and disaster recovery testing
- [ ] Load testing with realistic traffic
- [ ] Documentation and operational handover

## Disaster Recovery Plan

### Recovery Time Objectives (RTO)
- **Database Recovery:** < 15 minutes (DO Managed DB restore)
- **Application Recovery:** < 5 minutes (Pod restart)
- **Full System Recovery:** < 30 minutes

### Recovery Point Objectives (RPO)
- **Database:** < 24 hours (daily backups)
- **Audit Logs:** < 24 hours (daily backup to DO Spaces)
- **Configuration:** 0 (Infrastructure as Code)

### Disaster Scenarios
1. **Pod Failure:** Automatic restart by Kubernetes
2. **Node Failure:** Pod rescheduling to healthy nodes
3. **Database Failure:** DO Managed PostgreSQL automatic failover
4. **Region Failure:** Manual restore in secondary region

## Security Compliance (FERPA)

### Data Protection Measures
- **Encryption at Rest:** DO Block Storage encrypted by default
- **Encryption in Transit:** TLS 1.3 for all connections
- **Database Security:** DO Managed PostgreSQL with SSL required
- **Network Isolation:** Cilium network policies
- **Audit Trail:** Immutable logging to persistent storage

### Access Controls
```yaml
# RBAC for application access
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: opendismissal-app
  namespace: opendismissal
rules:
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list"]
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: opendismissal-binding
  namespace: opendismissal
subjects:
  - kind: ServiceAccount
    name: opendismissal-sa
    namespace: opendismissal
roleRef:
  kind: Role
  name: opendismissal-app
  apiGroup: rbac.authorization.k8s.io
```

## Success Metrics

### Performance Targets
- **Application Response Time:** < 200ms (95th percentile) at dismiss.hatchertechnology.com
- **Database Query Performance:** < 50ms average
- **WebSocket Connection Time:** < 100ms
- **System Uptime:** 99.9% availability
- **SSL Certificate Health:** Automatic renewal 30 days before expiry

### Cost Efficiency
- **Monthly Cost:** < $100 for production environment
- **Cost per Student:** < $0.10 per student per month
- **Resource Utilization:** > 70% average CPU/memory usage

### Security and Compliance
- **Zero Unencrypted Data:** All data encrypted at rest and in transit
- **Complete Audit Trail:** 100% of student data access logged
- **Access Control:** Role-based access with principle of least privilege
- **Incident Response Time:** < 15 minutes for security alerts

## Next Steps

1. **Provision DO Managed PostgreSQL** and configure connection strings
2. **Set up DOCR** and build optimized container images
3. **Deploy basic application** with DO Load Balancer integration
4. **Configure monitoring** and alerting systems
5. **Implement backup procedures** and test disaster recovery
6. **Conduct security assessment** and compliance validation
7. **Performance testing** and optimization
8. **Production deployment** with gradual traffic migration

---

**Note:** This plan is specifically optimized for DigitalOcean Managed Kubernetes Service and takes advantage of DO-native features for cost efficiency, performance, and operational simplicity. The hybrid approach (managed database + in-cluster Redis) provides the best balance of cost, performance, and operational overhead for a school dismissal system.