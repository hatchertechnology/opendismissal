#!/bin/bash
# Create Kubernetes secrets for OpenDismissal deployment
# This script generates secure secrets and applies them directly to K8s
# WITHOUT storing them in version control

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Creating Kubernetes secrets for OpenDismissal...${NC}"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl is required but not installed${NC}"
    exit 1
fi

# Check if we can connect to the cluster
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}Error: Cannot connect to Kubernetes cluster${NC}"
    exit 1
fi

# Generate secure secrets
echo -e "${YELLOW}Generating secure secrets...${NC}"

# Django secret key (50 chars URL-safe)
DJANGO_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")

# PostgreSQL password (32 bytes random)
POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d '\n')

# Prompt for Cloudflare API token
echo -e "${YELLOW}Please enter your Cloudflare API token:${NC}"
read -s CLOUDFLARE_API_TOKEN

if [ -z "$CLOUDFLARE_API_TOKEN" ]; then
    echo -e "${RED}Error: Cloudflare API token is required${NC}"
    exit 1
fi

# Django superuser credentials
echo -e "${YELLOW}Enter Django superuser username (default: admin):${NC}"
read DJANGO_SUPERUSER_USERNAME
DJANGO_SUPERUSER_USERNAME=${DJANGO_SUPERUSER_USERNAME:-admin}

echo -e "${YELLOW}Enter Django superuser email:${NC}"
read DJANGO_SUPERUSER_EMAIL

echo -e "${YELLOW}Enter Django superuser password:${NC}"
read -s DJANGO_SUPERUSER_PASSWORD

if [ -z "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo -e "${RED}Error: Django superuser password is required${NC}"
    exit 1
fi

# Create the secret directly in Kubernetes
echo -e "${YELLOW}Creating secret in Kubernetes cluster...${NC}"

kubectl create secret generic django-secrets \
    --namespace=opendismissal-demo \
    --from-literal=SECRET_KEY="$DJANGO_SECRET_KEY" \
    --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
    --from-literal=CLOUDFLARE_API_TOKEN="$CLOUDFLARE_API_TOKEN" \
    --from-literal=DJANGO_SUPERUSER_USERNAME="$DJANGO_SUPERUSER_USERNAME" \
    --from-literal=DJANGO_SUPERUSER_PASSWORD="$DJANGO_SUPERUSER_PASSWORD" \
    --from-literal=DJANGO_SUPERUSER_EMAIL="$DJANGO_SUPERUSER_EMAIL" \
    --dry-run=client -o yaml | kubectl apply -f -

# Add labels to the secret
kubectl label secret django-secrets \
    --namespace=opendismissal-demo \
    app.kubernetes.io/name=opendismissal \
    app.kubernetes.io/version=1.0.0 \
    app.kubernetes.io/component=secret \
    app.kubernetes.io/part-of=opendismissal-demo \
    --overwrite

# Add annotations
kubectl annotate secret django-secrets \
    --namespace=opendismissal-demo \
    kubernetes.io/description="Django application secrets" \
    --overwrite

echo -e "${GREEN}✓ Django secrets created successfully in Kubernetes${NC}"
echo -e "${YELLOW}Remember to store the PostgreSQL password securely: $POSTGRES_PASSWORD${NC}"
echo -e "${YELLOW}You can retrieve secrets later with: kubectl get secret django-secrets -n opendismissal-demo -o yaml${NC}"

# Clear variables from memory
unset DJANGO_SECRET_KEY POSTGRES_PASSWORD CLOUDFLARE_API_TOKEN DJANGO_SUPERUSER_PASSWORD