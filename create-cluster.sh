#!/usr/bin/env sh

# Variables
KIND_CONFIG="./k8s/kind-config.yaml"
HIVEBOX_IMAGE="hivebox:latest"
HIVEBOX_DEPLOY="./k8s/hivebox-deploy.yaml"
NGINX_DEPLOY="./k8s/nginx-deploy.yaml"

# Check for kind
if ! type kind > /dev/null 2>&1
then
    echo "Kind could not be found. Please install kind before running this script."
    exit 1
fi

# Check for kubectl
if ! type kubectl > /dev/null 2>&1
then
    echo "kubectl could not be found. Please install kubectl before running this script."
    exit 1
fi

# Create cluster
echo "Creating Kubernetes cluster with kind..."
kind create cluster --config "$KIND_CONFIG" --verbosity 4

# Load image
echo "Loading $HIVEBOX_IMAGE into the cluster..."
kind load docker-image "$HIVEBOX_IMAGE" || exit 1

# Apply resources
echo "Applying hivebox resources from $HIVEBOX_DEPLOY..."
kubectl apply -f "$HIVEBOX_DEPLOY" || exit 1

# Deploy nginx
echo "Deploying nginx ingress controller from $NGINX_DEPLOY..."
kubectl apply -f "$NGINX_DEPLOY" || exit 1
