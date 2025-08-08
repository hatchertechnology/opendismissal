#!/bin/bash
# Generate secure secrets for OpenDismissal Kubernetes deployment
# This script creates properly formatted and URL-encoded secrets

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== OpenDismissal Secret Generator ===${NC}"
echo

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is required but not installed${NC}"
    exit 1
fi

# Check if openssl is available
if ! command -v openssl &> /dev/null; then
    echo -e "${RED}Error: openssl is required but not installed${NC}"
    exit 1
fi

# Configuration
NAMESPACE="${NAMESPACE:-opendismissal-demo}"
OUTPUT_FILE="${1:-k8s/overlays/demo/secret.yaml}"

echo -e "${YELLOW}Generating secrets for namespace: ${NAMESPACE}${NC}"
echo -e "${YELLOW}Output file: ${OUTPUT_FILE}${NC}"
echo

# Generate secrets
echo "Generating Django SECRET_KEY..."
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")

echo "Generating PostgreSQL password..."
POSTGRES_PASSWORD_RAW=$(openssl rand -base64 32)
# URL encode the password for DATABASE_URL
POSTGRES_PASSWORD_ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('${POSTGRES_PASSWORD_RAW}'))")

echo "Generating Django superuser password..."
SUPERUSER_PASSWORD=$(openssl rand -base64 24)

echo "Generating secure usernames..."
SUPERUSER_USERNAME="admin$(openssl rand -hex 4)"

# Get user input for required fields
echo
echo -e "${YELLOW}Please provide the following information:${NC}"
read -p "Admin email address: " ADMIN_EMAIL
read -p "Cloudflare API token (or press Enter to use placeholder): " CLOUDFLARE_TOKEN

# Use placeholder if no token provided
if [ -z "$CLOUDFLARE_TOKEN" ]; then
    CLOUDFLARE_TOKEN="REPLACE-WITH-ACTUAL-CLOUDFLARE-TOKEN"
    echo -e "${YELLOW}Using placeholder for Cloudflare token - remember to update before deployment!${NC}"
fi

# Create the secret file
cat > "$OUTPUT_FILE" << EOF
# SECURITY WARNING: This file contains sensitive credentials
# DO NOT commit this file to version control
# Generated: $(date -u '+%Y-%m-%d %H:%M:%S UTC')
#
# To apply: kubectl apply -f ${OUTPUT_FILE}
# To rotate: Run this script again and reapply
#
apiVersion: v1
kind: Secret
metadata:
  name: django-secrets
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/name: opendismissal
    app.kubernetes.io/component: secret
  annotations:
    generated-by: "generate-secrets.sh"
    generated-at: "$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
type: Opaque
stringData:
  # Django secret key (auto-generated, cryptographically secure)
  SECRET_KEY: "${SECRET_KEY}"
  
  # PostgreSQL password (auto-generated, cryptographically secure)
  # Raw password for POSTGRES_PASSWORD env var
  POSTGRES_PASSWORD: "${POSTGRES_PASSWORD_RAW}"
  
  # Cloudflare API token for External DNS
  # Required permissions: Zone:Read + DNS:Edit
  CLOUDFLARE_API_TOKEN: "${CLOUDFLARE_TOKEN}"
  
  # Initial Django superuser (change immediately after first login)
  DJANGO_SUPERUSER_USERNAME: "${SUPERUSER_USERNAME}"
  DJANGO_SUPERUSER_PASSWORD: "${SUPERUSER_PASSWORD}"
  DJANGO_SUPERUSER_EMAIL: "${ADMIN_EMAIL}"
  
  # Database URL with properly URL-encoded password
  # IMPORTANT: Password is URL-encoded to handle special characters
  DATABASE_URL: "postgresql://django_user:${POSTGRES_PASSWORD_ENCODED}@postgresql-service-demo:5432/opendismissal?sslmode=disable"
EOF

# Set proper permissions
chmod 600 "$OUTPUT_FILE"

echo
echo -e "${GREEN}✅ Secret file generated successfully!${NC}"
echo
echo "Generated credentials:"
echo "====================="
echo "Django Admin Username: ${SUPERUSER_USERNAME}"
echo "Django Admin Password: ${SUPERUSER_PASSWORD}"
echo "Django Admin Email: ${ADMIN_EMAIL}"
echo
echo -e "${YELLOW}⚠️  IMPORTANT NOTES:${NC}"
echo "1. The secret file contains sensitive data - do not commit to git"
echo "2. Change the superuser password immediately after first login"
echo "3. If Cloudflare token was not provided, update it before deployment"
echo "4. The PostgreSQL password is automatically URL-encoded in DATABASE_URL"
echo
echo "To apply the secret:"
echo "  kubectl apply -f ${OUTPUT_FILE}"
echo
echo "To verify the secret:"
echo "  kubectl get secret django-secrets -n ${NAMESPACE}"