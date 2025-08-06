#!/bin/bash

# Build and push script for OpenDismissal container image
# This script builds the Docker image and pushes it to GitHub Container Registry

set -e  # Exit on any error

# Show help
show_help() {
    echo "Usage: $0 [VERSION]"
    echo ""
    echo "Build and push OpenDismissal container image to GitHub Container Registry"
    echo ""
    echo "Arguments:"
    echo "  VERSION    Optional version tag (default: latest or git tag)"
    echo ""
    echo "Examples:"
    echo "  $0              # Build with latest or git tag"
    echo "  $0 v1.0.0       # Build with specific version"
    echo "  $0 latest       # Build with latest tag"
    echo ""
    echo "Prerequisites:"
    echo "  - Docker installed and running"
    echo "  - GitHub Personal Access Token with 'write:packages' scope"
    echo "  - Logged in to ghcr.io: docker login ghcr.io -u YOUR_GITHUB_USERNAME"
    exit 0
}

# Check for help flag
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    show_help
fi

# Validate version tag format
validate_version() {
    local version="$1"
    if [[ ! "$version" =~ ^[a-zA-Z0-9._-]+$ ]]; then
        echo "❌ Error: Invalid version tag format: $version"
        echo "Version tags can only contain letters, numbers, dots, underscores, and hyphens"
        exit 1
    fi
}

# Configuration
REGISTRY="ghcr.io"
OWNER="hatchertechnology"
REPO="opendismissal"
IMAGE_NAME="${REGISTRY}/${OWNER}/${REPO}"
BUILD_DSKEY=$(pwgen -s 32 1)

# Get version from argument, git tag, or use 'latest' as default
VERSION=${1:-$(git describe --tags --always 2>/dev/null || echo "latest")}

# Validate version
validate_version "$VERSION"

# Full image tag
FULL_TAG="${IMAGE_NAME}:${VERSION}"
LATEST_TAG="${IMAGE_NAME}:latest"

echo "Building OpenDismissal container image..."
echo "Registry: ${REGISTRY}"
echo "Image: ${IMAGE_NAME}"
echo "Version: ${VERSION}"
echo "Full tag: ${FULL_TAG}"

# Build the Docker image
echo "Building Docker image..."

docker buildx build -t "${FULL_TAG}"  --secret id=BUILD_DSKEY,env=BUILD_DSKEY .

# Tag as latest if this is not already latest
if [ "${VERSION}" != "latest" ]; then
    echo "Tagging as latest..."
    docker tag "${FULL_TAG}" "${LATEST_TAG}"
fi

# Login to GitHub Container Registry
echo "Logging in to GitHub Container Registry..."
echo "Please ensure you have a GitHub Personal Access Token with 'write:packages' scope"
echo "You can create one at: https://github.com/settings/tokens"

# Check if already logged in
if ! docker info | grep -q "ghcr.io"; then
    echo "Please log in to GitHub Container Registry:"
    echo "docker login ghcr.io -u YOUR_GITHUB_USERNAME"
    read -p "Press Enter after logging in, or Ctrl+C to cancel..."
fi

# Push the image
echo "Pushing image to registry..."
docker push "${FULL_TAG}"

if [ "${VERSION}" != "latest" ]; then
    echo "Pushing latest tag..."
    docker push "${LATEST_TAG}"
fi

echo "✅ Successfully built and pushed:"
echo "   ${FULL_TAG}"
if [ "${VERSION}" != "latest" ]; then
    echo "   ${LATEST_TAG}"
fi

echo ""
echo "To use this image in docker-compose:"
echo "  image: ${FULL_TAG}"
echo ""
echo "To pull and run manually:"
echo "  docker pull ${FULL_TAG}"
echo "  docker run -p 8000:8000 ${FULL_TAG}"
