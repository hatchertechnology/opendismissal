#!/bin/bash

# OpenDismissal Kubernetes Deployment Script
# This script deploys the OpenDismissal application to a Kubernetes cluster

set -e

echo "OpenDismissal Kubernetes Deployment"
echo "==================================="

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl is not installed or not in PATH"
    exit 1
fi

# Check if doctl is available for DOCR authentication
if ! command -v doctl &> /dev/null; then
    echo "Error: doctl is not installed or not in PATH"
    exit 1
fi

# Function to create DOCR secret
create_docr_secret() {
    echo "Creating DigitalOcean Container Registry secret..."
    
    # Get the Docker config from doctl and create the secret
    DOCKER_CONFIG=$(doctl registry docker-config | base64 -w 0)
    
    # Create the secret YAML temporarily
    cat > /tmp/docr-secret.yaml << EOF
apiVersion: v1
kind: Secret
metadata:
  name: docr-secret
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: ${DOCKER_CONFIG}
EOF
    
    kubectl apply -f /tmp/docr-secret.yaml
    rm /tmp/docr-secret.yaml
    echo "DOCR secret created successfully"
}

# Function to generate Django secret key
generate_secret_key() {
    python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
}

# Function to create application secrets
create_app_secrets() {
    echo "Creating application secrets..."
    
    # Check if secrets already exist
    if kubectl get secret opendismissal-secrets &> /dev/null; then
        echo "Application secrets already exist. Skipping creation."
        return
    fi
    
    # Prompt for database URL
    read -p "Enter PostgreSQL database URL (e.g., postgresql://user:pass@host:5432/db): " DATABASE_URL
    
    # Generate secret key
    SECRET_KEY=$(generate_secret_key)
    echo "Generated Django secret key"
    
    # Prompt for Redis URL
    read -p "Enter Redis URL (e.g., redis://redis-host:6379/0): " REDIS_URL
    
    # Create the secret
    kubectl create secret generic opendismissal-secrets \
        --from-literal=database-url="${DATABASE_URL}" \
        --from-literal=secret-key="${SECRET_KEY}" \
        --from-literal=redis-url="${REDIS_URL}"
    
    echo "Application secrets created successfully"
}

# Function to deploy the application
deploy_app() {
    echo "Deploying OpenDismissal application..."
    
    # Apply the deployment
    kubectl apply -f k8s-deployment.yaml
    
    echo "Deployment applied successfully"
    echo ""
    echo "Checking deployment status..."
    kubectl rollout status deployment/opendismissal
    
    echo ""
    echo "Getting service information..."
    kubectl get svc opendismissal-service
    
    echo ""
    echo "Getting pod information..."
    kubectl get pods -l app=opendismissal
}

# Function to show logs
show_logs() {
    echo "Recent logs from OpenDismissal pods:"
    kubectl logs -l app=opendismissal --tail=50
}

# Main deployment process
main() {
    case "${1:-deploy}" in
        "deploy")
            create_docr_secret
            create_app_secrets
            deploy_app
            ;;
        "logs")
            show_logs
            ;;
        "status")
            kubectl get all -l app=opendismissal
            ;;
        "delete")
            echo "Deleting OpenDismissal deployment..."
            kubectl delete -f k8s-deployment.yaml
            kubectl delete secret opendismissal-secrets docr-secret
            echo "Deployment deleted"
            ;;
        *)
            echo "Usage: $0 [deploy|logs|status|delete]"
            echo ""
            echo "Commands:"
            echo "  deploy  - Deploy the application (default)"
            echo "  logs    - Show recent application logs"
            echo "  status  - Show deployment status"
            echo "  delete  - Delete the deployment and secrets"
            exit 1
            ;;
    esac
}

main "$@"