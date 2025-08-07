#!/bin/bash
# Script to generate secure Kubernetes secrets for OpenDismissal
# This script generates cryptographically secure random values
# NEVER commit the generated secret.yaml file to version control

set -euo pipefail

NAMESPACE="${1:-opendismissal-demo}"
OUTPUT_FILE="${2:-k8s/overlays/demo/secret.yaml}"

echo "========================================="
echo "Secure Secret Generation for OpenDismissal"
echo "========================================="
echo "Namespace: $NAMESPACE"
echo "Output file: $OUTPUT_FILE"
echo ""

# Check if output file already exists
if [ -f "$OUTPUT_FILE" ]; then
    read -p "WARNING: $OUTPUT_FILE already exists. Overwrite? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted. No changes made."
        exit 1
    fi
fi

# Generate secure random values
echo "Generating secure random values..."

# Django Secret Key (50 chars URL-safe base64)
DJANGO_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")

# PostgreSQL Password (32 bytes base64 encoded)
POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d '\n')

# Admin Password (24 bytes base64, URL-safe characters)
ADMIN_PASSWORD=$(openssl rand -base64 24 | tr -d '\n' | tr '+/' '-_')

# Generate timestamp for audit
GENERATED_AT=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

# Create the secret YAML
cat > "$OUTPUT_FILE" << EOF
# SECURITY WARNING: This file contains sensitive credentials
# DO NOT commit this file to version control
# Generated: $GENERATED_AT
#
# To apply: kubectl apply -f $OUTPUT_FILE
# To rotate: Run this script again and reapply
#
apiVersion: v1
kind: Secret
metadata:
  name: django-secrets
  namespace: $NAMESPACE
  labels:
    app.kubernetes.io/name: opendismissal
    app.kubernetes.io/component: secret
  annotations:
    generated-by: "generate-secure-secrets.sh"
    generated-at: "$GENERATED_AT"
type: Opaque
stringData:
  # Django secret key (auto-generated, cryptographically secure)
  SECRET_KEY: "$DJANGO_SECRET_KEY"
  
  # PostgreSQL password (auto-generated, cryptographically secure)
  POSTGRES_PASSWORD: "$POSTGRES_PASSWORD"
  
  # Cloudflare API token - MUST be manually added
  # Get from: https://dash.cloudflare.com/profile/api-tokens
  CLOUDFLARE_API_TOKEN: "REPLACE-WITH-ACTUAL-CLOUDFLARE-TOKEN"
  
  # Initial Django superuser (change immediately after first login)
  DJANGO_SUPERUSER_USERNAME: "initialadmin"
  DJANGO_SUPERUSER_PASSWORD: "$ADMIN_PASSWORD"
  DJANGO_SUPERUSER_EMAIL: "admin@example.com"
  
  # Database URL with SSL required
  DATABASE_URL: "postgresql://django_user:$POSTGRES_PASSWORD@postgresql-service:5432/opendismissal?sslmode=require"
EOF

# Set restrictive permissions
chmod 600 "$OUTPUT_FILE"

echo ""
echo "✅ Secure secrets generated successfully!"
echo ""
echo "IMPORTANT NEXT STEPS:"
echo "1. Edit $OUTPUT_FILE and replace CLOUDFLARE_API_TOKEN with your actual token"
echo "2. Update DJANGO_SUPERUSER_EMAIL with a valid email address"
echo "3. Apply the secret: kubectl apply -f $OUTPUT_FILE"
echo "4. After deployment, immediately change the admin password via Django admin"
echo ""
echo "Generated credentials (save these securely):"
echo "  Initial Admin Username: initialadmin"
echo "  Initial Admin Password: $ADMIN_PASSWORD"
echo ""
echo "⚠️  SECURITY REMINDERS:"
echo "  - NEVER commit $OUTPUT_FILE to version control"
echo "  - Rotate these credentials regularly"
echo "  - Use kubectl create secret for production deployments"
echo "  - Enable audit logging for all secret access"