#!/bin/bash

# AI Scalping EA - Production Deployment Script
# This script handles the complete deployment to Oracle Cloud

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="ai-scalping-ea"
DOCKER_USERNAME=${DOCKER_USERNAME:-"your_docker_username"}
ORACLE_HOST=${ORACLE_HOST:-"your_oracle_host"}
ORACLE_USER=${ORACLE_USER:-"ubuntu"}

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if required tools are installed
    command -v docker >/dev/null 2>&1 || { log_error "Docker is required but not installed."; exit 1; }
    command -v docker-compose >/dev/null 2>&1 || { log_error "Docker Compose is required but not installed."; exit 1; }

    # Check if .env file exists
    if [ ! -f ".env" ]; then
        log_error ".env file not found. Please copy .env.example to .env and configure your settings."
        exit 1
    fi

    log_success "Prerequisites check passed"
}

build_images() {
    log_info "Building Docker images..."

    # Build backend
    log_info "Building backend image..."
    docker build -t ${DOCKER_USERNAME}/ai-scalping-backend:latest ./backend

    # Build dashboard
    log_info "Building dashboard image..."
    docker build -t ${DOCKER_USERNAME}/ai-scalping-dashboard:latest ./dashboard

    log_success "Images built successfully"
}

push_images() {
    log_info "Pushing images to Docker Hub..."

    # Login to Docker Hub
    echo "Logging in to Docker Hub..."
    docker login -u ${DOCKER_USERNAME}

    # Push images
    docker push ${DOCKER_USERNAME}/ai-scalping-backend:latest
    docker push ${DOCKER_USERNAME}/ai-scalping-dashboard:latest

    log_success "Images pushed successfully"
}

deploy_to_oracle() {
    log_info "Deploying to Oracle Cloud..."

    # Create deployment script for remote execution
    cat > deploy_remote.sh << 'EOF'
#!/bin/bash
set -e

PROJECT_DIR="/home/ubuntu/ai-scalping-ea"
BACKUP_DIR="/home/ubuntu/backups"

# Create backup directory
mkdir -p $BACKUP_DIR

# Navigate to project directory
cd $PROJECT_DIR

# Create backup of current .env
if [ -f ".env" ]; then
    cp .env $BACKUP_DIR/.env.backup-$(date +%Y%m%d_%H%M%S)
fi

# Pull latest code
echo "Pulling latest code..."
git pull origin main

# Copy new .env if provided
if [ -f ".env.new" ]; then
    cp .env.new .env
    rm .env.new
fi

# Pull latest images
echo "Pulling latest images..."
docker pull DOCKER_USERNAME_PLACEHOLDER/ai-scalping-backend:latest
docker pull DOCKER_USERNAME_PLACEHOLDER/ai-scalping-dashboard:latest

# Tag for local use
docker tag DOCKER_USERNAME_PLACEHOLDER/ai-scalping-backend:latest ai-scalping-backend:latest
docker tag DOCKER_USERNAME_PLACEHOLDER/ai-scalping-dashboard:latest ai-scalping-dashboard:latest

# Stop services gracefully
echo "Stopping current services..."
docker-compose stop ai_backend streamlit || true

# Start with new images
echo "Starting services with new images..."
docker-compose up -d --no-deps ai_backend streamlit

# Wait for services
echo "Waiting for services to start..."
sleep 30

# Health checks
echo "Performing health checks..."
if curl -f http://localhost:8000/health && curl -f http://localhost:8501/_stcore/health; then
    echo "✅ Deployment successful!"
    
    # Clean up old images
    docker image prune -f
    
    exit 0
else
    echo "❌ Health checks failed, rolling back..."
    
    # Rollback
    docker-compose stop ai_backend streamlit
    docker-compose up -d ai_backend streamlit
    
    exit 1
fi
EOF

    # Replace placeholder
    sed -i "s/DOCKER_USERNAME_PLACEHOLDER/${DOCKER_USERNAME}/g" deploy_remote.sh

    # Copy files to Oracle Cloud
    log_info "Copying files to Oracle Cloud..."
    scp -o StrictHostKeyChecking=no -i ~/.ssh/oracle_key .env ubuntu@${ORACLE_HOST}:~/ai-scalping-ea/.env.new
    scp -o StrictHostKeyChecking=no -i ~/.ssh/oracle_key deploy_remote.sh ubuntu@${ORACLE_HOST}:~/deploy.sh
    scp -o StrictHostKeyChecking=no -i ~/.ssh/oracle_key docker-compose.yml ubuntu@${ORACLE_HOST}:~/ai-scalping-ea/

    # Execute deployment on remote server
    log_info "Executing deployment on Oracle Cloud..."
    ssh -o StrictHostKeyChecking=no -i ~/.ssh/oracle_key ubuntu@${ORACLE_HOST} "chmod +x ~/deploy.sh && ~/deploy.sh"

    # Cleanup
    rm deploy_remote.sh

    log_success "Deployment completed successfully"
}

rollback() {
    log_info "Rolling back deployment..."

    # Rollback script for remote execution
    cat > rollback_remote.sh << 'EOF'
#!/bin/bash
cd /home/ubuntu/ai-scalping-ea

echo "Stopping current services..."
docker-compose stop ai_backend streamlit

echo "Starting services with previous images..."
docker-compose up -d ai_backend streamlit

echo "Rollback completed"
EOF

    # Execute rollback
    scp -o StrictHostKeyChecking=no -i ~/.ssh/oracle_key rollback_remote.sh ubuntu@${ORACLE_HOST}:~/rollback.sh
    ssh -o StrictHostKeyChecking=no -i ~/.ssh/oracle_key ubuntu@${ORACLE_HOST} "chmod +x ~/rollback.sh && ~/rollback.sh"

    # Cleanup
    rm rollback_remote.sh

    log_success "Rollback completed"
}

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -b, --build     Build Docker images"
    echo "  -p, --push      Push images to Docker Hub"
    echo "  -d, --deploy    Deploy to Oracle Cloud"
    echo "  -r, --rollback  Rollback deployment"
    echo "  -a, --all       Build, push and deploy"
    echo "  -h, --help      Show this help"
    echo ""
    echo "Environment variables:"
    echo "  DOCKER_USERNAME  Your Docker Hub username"
    echo "  ORACLE_HOST      Oracle Cloud host IP"
    echo "  ORACLE_USER      Oracle Cloud username (default: ubuntu)"
}

# Main script
case "${1:-all}" in
    -b|--build)
        check_prerequisites
        build_images
        ;;
    -p|--push)
        check_prerequisites
        push_images
        ;;
    -d|--deploy)
        check_prerequisites
        deploy_to_oracle
        ;;
    -r|--rollback)
        rollback
        ;;
    -a|--all)
        check_prerequisites
        build_images
        push_images
        deploy_to_oracle
        ;;
    -h|--help|*)
        show_usage
        ;;
esac