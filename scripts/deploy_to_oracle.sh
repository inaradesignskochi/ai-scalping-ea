#!/bin/bash
# Deployment script for Oracle Cloud Always Free tier
# This script sets up the complete AI Scalping EA system

set -e  # Exit on any error

echo "🚀 Starting AI Scalping EA deployment to Oracle Cloud..."

# Configuration
PROJECT_NAME="ai-scalping-ea"
ORACLE_REGION="us-ashburn-1"
INSTANCE_SHAPE="VM.Standard.A1.Flex"
OCPUS=4
MEMORY_IN_GBS=24
BOOT_VOLUME_SIZE_IN_GB=100

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if OCI CLI is installed
    if ! command -v oci &> /dev/null; then
        print_error "OCI CLI is not installed. Please install it first."
        print_status "Installation guide: https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm"
        exit 1
    fi
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        print_status "Installation guide: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    # Check if Git is installed
    if ! command -v git &> /dev/null; then
        print_error "Git is not installed. Please install Git first."
        exit 1
    fi
    
    print_status "All prerequisites met."
}

# Setup Oracle Cloud Infrastructure
setup_oci_infrastructure() {
    print_status "Setting up Oracle Cloud Infrastructure..."
    
    # Create VCN if it doesn't exist
    VCN_ID=$(oci network vcn create \
        --compartment-id $COMPARTMENT_ID \
        --display-name "${PROJECT_NAME}-vcn" \
        --cidr-block "10.0.0.0/16" \
        --dns-label "${PROJECT_NAME}vcn" \
        --query "data.id" \
        --raw-output)
    
    print_status "VCN created: $VCN_ID"
    
    # Create internet gateway
    IG_ID=$(oci network internet-gateway create \
        --compartment-id $COMPARTMENT_ID \
        --vcn-id $VCN_ID \
        --display-name "${PROJECT_NAME}-ig" \
        --is-enabled true \
        --query "data.id" \
        --raw-output)
    
    print_status "Internet Gateway created: $IG_ID"
    
    # Create route table
    ROUTE_TABLE_ID=$(oci network route-table create \
        --compartment-id $COMPARTMENT_ID \
        --vcn-id $VCN_ID \
        --display-name "${PROJECT_NAME}-rt" \
        --route-rules "[{\"destinationType\":\"INTERNET\",\"destination\":\"0.0.0.0/0\",\"networkEntityId\":\"$IG_ID\"}]" \
        --query "data.id" \
        --raw-output)
    
    print_status "Route Table created: $ROUTE_TABLE_ID"
    
    # Create security list with required ports
    SECURITY_LIST_ID=$(oci network security-list create \
        --compartment-id $COMPARTMENT_ID \
        --vcn-id $VCN_ID \
        --display-name "${PROJECT_NAME}-sl" \
        --ingress-security-rules '[{"sourceType":"CIDR","source":"0.0.0.0/0","protocol":"6","tcpOptions":{"destinationPortRange":{"min":22,"max":22}}},{"sourceType":"CIDR","source":"0.0.0.0/0","protocol":"6","tcpOptions":{"destinationPortRange":{"min":80,"max":80}}},{"sourceType":"CIDR","source":"0.0.0.0/0","protocol":"6","tcpOptions":{"destinationPortRange":{"min":443,"max":443}}},{"sourceType":"CIDR","source":"0.0.0.0/0","protocol":"6","tcpOptions":{"destinationPortRange":{"min":5555,"max":5556}}},{"sourceType":"CIDR","source":"0.0.0.0/0","protocol":"6","tcpOptions":{"destinationPortRange":{"min":8501,"max":8501}}},{"sourceType":"CIDR","source":"0.0.0.0/0","protocol":"6","tcpOptions":{"destinationPortRange":{"min":3000,"max":3000}}},{"sourceType":"CIDR","source":"0.0.0.0/0","protocol":"6","tcpOptions":{"destinationPortRange":{"min":9090,"max":9090}}}]' \
        --egress-security-rules '[{"destinationType":"CIDR","destination":"0.0.0.0/0","protocol":"ALL"}]' \
        --query "data.id" \
        --raw-output)
    
    print_status "Security List created: $SECURITY_LIST_ID"
    
    # Create subnet
    SUBNET_ID=$(oci network subnet create \
        --compartment-id $COMPARTMENT_ID \
        --vcn-id $VCN_ID \
        --display-name "${PROJECT_NAME}-subnet" \
        --cidr-block "10.0.1.0/24" \
        --security-list-ids "[\"$SECURITY_LIST_ID\"]" \
        --route-table-id $ROUTE_TABLE_ID \
        --dns-label "${PROJECT_NAME}subnet" \
        --query "data.id" \
        --raw-output)
    
    print_status "Subnet created: $SUBNET_ID"
    
    echo "export VCN_ID=$VCN_ID" >> ~/.bashrc
    echo "export SUBNET_ID=$SUBNET_ID" >> ~/.bashrc
    echo "export SECURITY_LIST_ID=$SECURITY_LIST_ID" >> ~/.bashrc
}

# Create compute instance
create_instance() {
    print_status "Creating compute instance..."
    
    # Get latest Ubuntu image
    IMAGE_ID=$(oci compute image list \
        --compartment-id $COMPARTMENT_ID \
        --operating-system "Canonical Ubuntu" \
        --shape VM.Standard.A1.Flex \
        --query "data[?contains(\"display-name\", '22.04')] | [0].id" \
        --raw-output)
    
    # Get VCN and subnet from environment or create new ones
    if [ -z "$VCN_ID" ] || [ -z "$SUBNET_ID" ]; then
        setup_oci_infrastructure
    fi
    
    # Create compute instance
    INSTANCE_ID=$(oci compute instance launch \
        --compartment-id $COMPARTMENT_ID \
        --shape VM.Standard.A1.Flex \
        --subnet-id $SUBNET_ID \
        --display-name "${PROJECT_NAME}-instance" \
        --image-id $IMAGE_ID \
        --ssh-public-keys-file ~/.ssh/id_rsa.pub \
        --metadata '{"user_data": "$(echo '#!/bin/bash
apt update && apt install -y docker.io docker-compose git python3 python3-pip
systemctl start docker
systemctl enable docker
usermod -aG docker $USER
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
git clone https://github.com/yourusername/ai-scalping-ea.git
cd ai-scalping-ea
docker-compose up -d --build
' | base64 -w 0)"}' \
        --query "data.id" \
        --raw-output)
    
    print_status "Instance created: $INSTANCE_ID"
    
    # Wait for instance to be running
    oci compute instance get --instance-id $INSTANCE_ID --wait-for-state RUNNING
}

# Setup instance
setup_instance() {
    print_status "Setting up instance..."
    
    # Get public IP
    PUBLIC_IP=$(oci compute instance list-vnics \
        --instance-id $INSTANCE_ID \
        --query "data[0].public-ip" \
        --raw-output)
    
    print_status "Instance public IP: $PUBLIC_IP"
    
    # Wait for SSH to be available
    print_status "Waiting for SSH to be available..."
    for i in {1..30}; do
        if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ubuntu@$PUBLIC_IP "echo 'SSH ready'" &>/dev/null; then
            print_status "SSH is ready!"
            break
        fi
        if [ $i -eq 30 ]; then
            print_error "SSH not available after 30 attempts"
            exit 1
        fi
        sleep 10
    done
    
    # Setup instance
    ssh -o StrictHostKeyChecking=no ubuntu@$PUBLIC_IP << EOF
# Update system
sudo apt update && sudo apt upgrade -y

# Install additional dependencies
sudo apt install -y python3-pip python3-dev build-essential curl wget htop

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Clone repository (replace with your actual repository)
cd /home/ubuntu
git clone https://github.com/yourusername/ai-scalping-ea.git
cd ai-scalping-ea

# Create environment file
cat > .env << 'ENVEOF'
# Database Configuration
DB_PASSWORD=$(openssl rand -base64 32)
POSTGRES_DB=trading_db
POSTGRES_USER=trader

# AI APIs
GEMINI_API_KEY=your_gemini_api_key_here

# Monitoring
GRAFANA_PASSWORD=$(openssl rand -base64 32)

# Free Tier API Keys (add your keys)
ALPACA_API_KEY=your_alpaca_api_key
ALPACA_SECRET_KEY=your_alpaca_secret_key
MARKETAUX_API_KEY=your_marketaux_api_key

# Security
SECRET_KEY=$(openssl rand -base64 64)
JWT_SECRET_KEY=$(openssl rand -base64 64)

# Configuration
DATABASE_URL=postgresql://trader:\${DB_PASSWORD}@postgres:5432/trading_db
REDIS_URL=redis://redis:6379

# Ports
STREAMLIT_PORT=8501
GRAFANA_PORT=3000
PROMETHEUS_PORT=9090
ZMQ_SIGNAL_PORT=5555
ZMQ_HEARTBEAT_PORT=5556
WEBSOCKET_PORT=8765
ENVEOF

# Build and start services
sudo docker-compose up -d --build

# Check if services are running
sudo docker-compose ps
EOF
}

# Verify deployment
verify_deployment() {
    print_status "Verifying deployment..."
    
    # Get public IP
    PUBLIC_IP=$(oci compute instance list-vnics \
        --instance-id $INSTANCE_ID \
        --query "data[0].public-ip" \
        --raw-output)
    
    # Wait for services to start
    print_status "Waiting for services to start..."
    sleep 60
    
    # Check services
    services=(
        "http://$PUBLIC_IP:8501"
        "http://$PUBLIC_IP:3000"
        "http://$PUBLIC_IP:9090"
    )
    
    for service in "${services[@]}"; do
        print_status "Checking $service..."
        if curl -f -s --max-time 10 "$service" > /dev/null; then
            print_status "$service is accessible ✓"
        else
            print_warning "$service is not accessible yet"
        fi
    done
    
    print_status "Deployment completed successfully!"
    print_status "Access your services at:"
    echo "  - Streamlit Dashboard: http://$PUBLIC_IP:8501"
    echo "  - Grafana Monitoring: http://$PUBLIC_IP:3000 (admin/admin)"
    echo "  - Prometheus Metrics: http://$PUBLIC_IP:9090"
}

# Cleanup function
cleanup() {
    print_warning "Cleaning up resources..."
    
    if [ ! -z "$INSTANCE_ID" ]; then
        oci compute instance terminate --instance-id $INSTANCE_ID --force
        print_status "Instance terminated"
    fi
}

# Set trap for cleanup
trap cleanup EXIT

# Main execution
main() {
    echo "=========================================="
    echo "  AI Scalping EA - Oracle Cloud Deployer"
    echo "=========================================="
    
    # Check for required environment variables
    if [ -z "$COMPARTMENT_ID" ]; then
        print_error "COMPARTMENT_ID environment variable not set"
        print_status "Set it with: export COMPARTMENT_ID=<your-compartment-ocid>"
        exit 1
    fi
    
    check_prerequisites
    create_instance
    setup_instance
    verify_deployment
    
    print_status "🎉 Deployment completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Configure your API keys in the .env file"
    echo "2. Set up MT4 with the provided Expert Advisor"
    echo "3. Test the system on a demo account"
    echo "4. Monitor performance through Grafana dashboards"
    echo ""
    echo "For support, check the logs with:"
    echo "  ssh ubuntu@$PUBLIC_IP 'cd /home/ubuntu/ai-scalping-ea && docker-compose logs'"
}

# Run main function
main "$@"