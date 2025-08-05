#!/bin/bash

# OpenDismissal Docker Build and Push Script
# This script builds the Docker image and pushes it to DigitalOcean Container Registry

set -e

# Configuration
REGISTRY="registry.digitalocean.com/opendismissal"
APP_NAME="opendismissal"
TAG=${1:-latest}

echo "Building OpenDismissal Docker image..."
echo "Registry: $REGISTRY"
echo "Tag: $TAG"

# Build the Docker image
echo "Building image: $REGISTRY/$APP_NAME:$TAG"
docker build -t $REGISTRY/$APP_NAME:$TAG .

# Also tag with latest if not already latest
if [ "$TAG" != "latest" ]; then
    echo "Tagging as latest: $REGISTRY/$APP_NAME:latest"
    docker tag $REGISTRY/$APP_NAME:$TAG $REGISTRY/$APP_NAME:latest
fi

# Push to DOCR
echo "Pushing image to DigitalOcean Container Registry..."
docker push $REGISTRY/$APP_NAME:$TAG

if [ "$TAG" != "latest" ]; then
    echo "Pushing latest tag..."
    docker push $REGISTRY/$APP_NAME:latest
fi

echo "Successfully built and pushed image: $REGISTRY/$APP_NAME:$TAG"
echo ""
echo "To pull this image elsewhere, use:"
echo "  docker pull $REGISTRY/$APP_NAME:$TAG"
echo ""
echo "For Kubernetes deployment, use:"
echo "  image: $REGISTRY/$APP_NAME:$TAG"