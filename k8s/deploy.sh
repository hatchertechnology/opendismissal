#!/bin/bash
# OpenDismissal Kubernetes Deployment Script
# Handles prerequisites, secret generation, and deployment

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}    OpenDismissal Kubernetes Deployment${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo

# Configuration
NAMESPACE="opendismissal-demo"
OVERLAY_PATH="k8s/overlays/demo"

# Function to check if a deployment exists and is ready
check_deployment() {
    local namespace=$1
    local deployment=$2
    
    if kubectl get deployment -n "$namespace" "$deployment" &> /dev/null; then
        kubectl rollout status deployment/"$deployment" -n "$namespace" --timeout=30s &> /dev/null
        return $?
    else
        return 1
    fi
}

# Function to wait for a job to complete
wait_for_job() {
    local job=$1
    local namespace=$2
    local timeout=${3:-120}
    
    echo -n "Waiting for job $job..."
    kubectl wait --for=condition=complete --timeout="${timeout}s" job/"$job" -n "$namespace" 2>/dev/null || {
        echo -e " ${YELLOW}Still running${NC}"
        return 1
    }
    echo -e " ${GREEN}✓${NC}"
    return 0
}

echo -e "${YELLOW}Step 1: Checking Prerequisites${NC}"
echo "================================"

# Check kubectl connection
echo -n "Checking kubectl connection... "
if kubectl cluster-info &> /dev/null; then
    CLUSTER=$(kubectl config current-context)
    echo -e "${GREEN}✓${NC} Connected to: $CLUSTER"
else
    echo -e "${RED}✗${NC}"
    echo -e "${RED}Error: kubectl not configured or cluster not accessible${NC}"
    exit 1
fi

# Check cert-manager
echo -n "Checking cert-manager... "
if check_deployment "cert-manager" "cert-manager"; then
    echo -e "${GREEN}✓${NC} Installed"
else
    echo -e "${YELLOW}Not found${NC}"
    echo -e "${YELLOW}Installing cert-manager...${NC}"
    kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.2/cert-manager.yaml
    echo "Waiting for cert-manager to be ready..."
    kubectl wait --for=condition=available --timeout=120s deployment/cert-manager -n cert-manager
    kubectl wait --for=condition=available --timeout=120s deployment/cert-manager-webhook -n cert-manager
    kubectl wait --for=condition=available --timeout=120s deployment/cert-manager-cainjector -n cert-manager
    echo -e "${GREEN}✓${NC} cert-manager installed"
fi

# Check nginx-ingress
echo -n "Checking nginx-ingress-controller... "
if check_deployment "ingress-nginx" "ingress-nginx-controller"; then
    echo -e "${GREEN}✓${NC} Installed"
else
    echo -e "${YELLOW}Not found${NC}"
    echo -e "${YELLOW}Installing nginx-ingress-controller for Digital Ocean...${NC}"
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.0/deploy/static/provider/do/deploy.yaml
    echo "Waiting for nginx-ingress to be ready..."
    kubectl wait --for=condition=available --timeout=120s deployment/ingress-nginx-controller -n ingress-nginx
    echo -e "${GREEN}✓${NC} nginx-ingress-controller installed"
fi

# Check container image
echo -n "Checking container image availability... "
if docker manifest inspect ghcr.io/hatchertechnology/opendismissal:latest &> /dev/null; then
    echo -e "${GREEN}✓${NC} Image available"
else
    echo -e "${YELLOW}⚠${NC} Unable to verify (may still work if cluster can pull)"
fi

echo
echo -e "${YELLOW}Step 2: Secret Configuration${NC}"
echo "============================="

# Check if secrets exist
if [ ! -f "$OVERLAY_PATH/secret.yaml" ]; then
    echo -e "${YELLOW}Secret file not found. Running secret generator...${NC}"
    if [ -f "k8s/generate-secrets.sh" ]; then
        ./k8s/generate-secrets.sh "$OVERLAY_PATH/secret.yaml"
    else
        echo -e "${RED}Error: generate-secrets.sh not found${NC}"
        echo "Please create secrets manually or run generate-secrets.sh"
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} Secret file exists"
    echo -n "Checking for placeholder values... "
    if grep -q "REPLACE" "$OVERLAY_PATH/secret.yaml" 2>/dev/null; then
        echo -e "${YELLOW}Found placeholders${NC}"
        echo -e "${YELLOW}⚠ Warning: Secret file contains placeholder values${NC}"
        read -p "Do you want to regenerate secrets? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            ./k8s/generate-secrets.sh "$OVERLAY_PATH/secret.yaml"
        fi
    else
        echo -e "${GREEN}✓${NC} No placeholders found"
    fi
fi

echo
echo -e "${YELLOW}Step 3: Deploying Application${NC}"
echo "=============================="

# Validate manifests
echo -n "Validating Kubernetes manifests... "
if kubectl kustomize "$OVERLAY_PATH" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo -e "${RED}Error: Manifest validation failed${NC}"
    kubectl kustomize "$OVERLAY_PATH"
    exit 1
fi

# Deploy application
echo -e "${BLUE}Deploying OpenDismissal to namespace: $NAMESPACE${NC}"
kubectl apply -k "$OVERLAY_PATH" 2>&1 | while IFS= read -r line; do
    if [[ $line == *"created"* ]]; then
        echo -e "  ${GREEN}✓${NC} $line"
    elif [[ $line == *"configured"* ]] || [[ $line == *"unchanged"* ]]; then
        echo -e "  ${BLUE}○${NC} $line"
    elif [[ $line == *"error"* ]] || [[ $line == *"Error"* ]]; then
        echo -e "  ${RED}✗${NC} $line"
    elif [[ $line == *"Warning"* ]] || [[ $line == *"no matches for kind"* ]]; then
        echo -e "  ${YELLOW}⚠${NC} $line"
    else
        echo "  $line"
    fi
done

# Apply cert-manager issuers if they weren't applied
echo -n "Applying cert-manager issuers... "
if kubectl apply -f "$OVERLAY_PATH/cert-manager-issuers.yaml" 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${BLUE}Already exists${NC}"
fi

echo
echo -e "${YELLOW}Step 4: Monitoring Deployment${NC}"
echo "=============================="

# Wait for PostgreSQL
echo -n "Waiting for PostgreSQL... "
kubectl rollout status statefulset/postgresql-demo -n "$NAMESPACE" --timeout=120s &> /dev/null && echo -e "${GREEN}✓${NC}" || echo -e "${YELLOW}⚠${NC}"

# Wait for Redis
echo -n "Waiting for Redis... "
kubectl rollout status deployment/redis-demo -n "$NAMESPACE" --timeout=60s &> /dev/null && echo -e "${GREEN}✓${NC}" || echo -e "${YELLOW}⚠${NC}"

# Wait for migrations
wait_for_job "django-migrate-demo" "$NAMESPACE" 180

# Wait for Django deployment
echo -n "Waiting for Django application... "
kubectl rollout status deployment/django-demo -n "$NAMESPACE" --timeout=180s &> /dev/null && echo -e "${GREEN}✓${NC}" || echo -e "${YELLOW}⚠${NC}"

# Wait for External DNS
echo -n "Waiting for External DNS... "
kubectl rollout status deployment/external-dns-demo -n "$NAMESPACE" --timeout=60s &> /dev/null && echo -e "${GREEN}✓${NC}" || echo -e "${YELLOW}⚠${NC}"

# Check jobs
wait_for_job "create-superuser-demo" "$NAMESPACE" 60
wait_for_job "generate-demo-data-demo" "$NAMESPACE" 120

echo
echo -e "${YELLOW}Step 5: Verifying Deployment${NC}"
echo "============================="

# Get ingress info
echo "Checking ingress configuration..."
INGRESS_IP=$(kubectl get ingress django-ingress-demo -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")
INGRESS_HOST=$(kubectl get ingress django-ingress-demo -n "$NAMESPACE" -o jsonpath='{.spec.rules[0].host}' 2>/dev/null || echo "not configured")

echo -e "  Ingress IP: ${BLUE}$INGRESS_IP${NC}"
echo -e "  Hostname: ${BLUE}$INGRESS_HOST${NC}"

# Check certificate status
echo -n "Checking SSL certificate... "
CERT_READY=$(kubectl get certificate django-tls-cert -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "False")
if [ "$CERT_READY" = "True" ]; then
    echo -e "${GREEN}✓${NC} Ready"
else
    echo -e "${YELLOW}⚠${NC} Provisioning (this may take a few minutes)"
fi

# Get pod status
echo
echo "Pod Status:"
kubectl get pods -n "$NAMESPACE" --no-headers | while IFS= read -r line; do
    if [[ $line == *"Running"* ]] || [[ $line == *"Completed"* ]]; then
        echo -e "  ${GREEN}✓${NC} $line"
    elif [[ $line == *"Error"* ]] || [[ $line == *"CrashLoopBackOff"* ]]; then
        echo -e "  ${RED}✗${NC} $line"
    else
        echo -e "  ${YELLOW}○${NC} $line"
    fi
done

# Get admin credentials
echo
echo -e "${YELLOW}Step 6: Access Information${NC}"
echo "=========================="

if [ -f "$OVERLAY_PATH/secret.yaml" ]; then
    ADMIN_USER=$(grep "DJANGO_SUPERUSER_USERNAME:" "$OVERLAY_PATH/secret.yaml" | cut -d'"' -f2)
    ADMIN_PASS=$(grep "DJANGO_SUPERUSER_PASSWORD:" "$OVERLAY_PATH/secret.yaml" | cut -d'"' -f2)
    ADMIN_EMAIL=$(grep "DJANGO_SUPERUSER_EMAIL:" "$OVERLAY_PATH/secret.yaml" | cut -d'"' -f2)
    
    echo -e "${GREEN}Admin Access Credentials:${NC}"
    echo -e "  URL: ${BLUE}https://$INGRESS_HOST/admin/${NC}"
    echo -e "  Username: ${BLUE}$ADMIN_USER${NC}"
    echo -e "  Password: ${BLUE}$ADMIN_PASS${NC}"
    echo -e "  Email: ${BLUE}$ADMIN_EMAIL${NC}"
    echo
    echo -e "${YELLOW}⚠ IMPORTANT: Change the admin password after first login!${NC}"
fi

echo
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}    Deployment Complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo
echo "Next steps:"
echo "1. Wait for DNS propagation (1-10 minutes)"
echo "2. Verify SSL certificate is issued"
echo "3. Access the application at https://$INGRESS_HOST"
echo "4. Log in and change the admin password"
echo
echo "Useful commands:"
echo "  View logs: kubectl logs -f deployment/django-demo -n $NAMESPACE"
echo "  Check pods: kubectl get pods -n $NAMESPACE"
echo "  Port forward: kubectl port-forward -n $NAMESPACE service/django-service-demo 8080:80"