#!/bin/bash

# Simple MCP Agent A2A - Cloud Run Deployment Script

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🚀 Deploying Intent MCP Agent A2A to Cloud Run${NC}"
echo

# Configuration
SERVICE_NAME="icoraintent-a2a-agent"
REGION="europe-north1"
MEMORY="1Gi"
CPU="1"
TIMEOUT="300s"
MAX_INSTANCES="10"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Set your project ID here
PROJECT="deep-ground-462419-k0"

# Ensure gcloud is using the correct project
gcloud config set project $PROJECT

echo -e "${BLUE}Using project: $PROJECT${NC}"

echo -e "${BLUE}📋 Deployment Configuration:${NC}"
echo "  Project: $PROJECT"
echo "  Service: $SERVICE_NAME"
echo "  Region: $REGION"
echo "  Memory: $MEMORY"
echo "  CPU: $CPU"
echo "  Timeout: $TIMEOUT"
echo

# Set environment variables
export MCP_FUNCTION_URL="https://europe-north1-deep-ground-462419-k0.cloudfunctions.net/icoraintent-mcp-fastmcp"
export WIREMOCK_FUNCTION_URL="https://europe-north1-deep-ground-462419-k0.cloudfunctions.net/icoraintent-wiremock-fastapi"

# Prompt for Google API Key if not set
if [ -z "$GOOGLE_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  GOOGLE_API_KEY not set in environment${NC}"
    read -p "Enter your Google API Key: " GOOGLE_API_KEY
    export GOOGLE_API_KEY
fi

# Enable required APIs
echo -e "${BLUE}🔧 Enabling required APIs...${NC}"
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable artifactregistry.googleapis.com

# Build and deploy using Cloud Build
echo -e "${BLUE}📦 Building and deploying to Cloud Run...${NC}"
gcloud run deploy $SERVICE_NAME \
  --clear-base-image \
  --source . \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_API_KEY=$GOOGLE_API_KEY,MCP_FUNCTION_URL=$MCP_FUNCTION_URL,WIREMOCK_FUNCTION_URL=$WIREMOCK_FUNCTION_URL" \
  --memory $MEMORY \
  --cpu $CPU \
  --timeout $TIMEOUT \
  --max-instances $MAX_INSTANCES \
  --concurrency 80 \
  --port 8080

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)')

echo
echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo
echo -e "${BLUE}📋 Service Details:${NC}"
echo "  Service Name: $SERVICE_NAME"
echo "  Service URL: $SERVICE_URL"
echo "  Region: $REGION"
echo "  Memory: $MEMORY"
echo "  CPU: $CPU"
echo "  Max Instances: $MAX_INSTANCES"
echo
echo -e "${BLUE}🧪 Test your service:${NC}"
echo "  Health Check:"
echo "    curl $SERVICE_URL"
echo
echo "  Create Intent via A2A Client:"
echo "    Use the A2A CLI or UI to connect to: $SERVICE_URL"
echo
echo -e "${BLUE}🎯 Example queries to try:${NC}"
echo "  - 'Create a 4K live broadcast intent for 1000 participants'"
echo "  - 'Check system status'"
echo "  - 'Test the complete workflow'"
echo "  - 'Set up a video conference intent for tomorrow'"
echo
echo -e "${GREEN}🎉 Your Intent MCP Agent A2A is now running on Cloud Run!${NC}"