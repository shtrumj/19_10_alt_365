#!/bin/bash

# 365 Email System SSL Setup Script for Mac/Linux
# This script sets up SSL certificates using Cloudflare DNS challenge

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values
DOMAIN="owa.shtrum.com"
CLOUDFLARE_EMAIL=""
CLOUDFLARE_API_KEY=""

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 -e <email> -k <api-key> [-d <domain>]"
    echo ""
    echo "Options:"
    echo "  -e, --email     Cloudflare email address"
    echo "  -k, --api-key   Cloudflare API key"
    echo "  -d, --domain    Domain name (default: owa.shtrum.com)"
    echo "  -h, --help      Show this help message"
    echo ""
    echo "Example:"
    echo "  $0 -e admin@example.com -k your-api-key"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--email)
            CLOUDFLARE_EMAIL="$2"
            shift 2
            ;;
        -k|--api-key)
            CLOUDFLARE_API_KEY="$2"
            shift 2
            ;;
        -d|--domain)
            DOMAIN="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Check if required parameters are provided
if [[ -z "$CLOUDFLARE_EMAIL" || -z "$CLOUDFLARE_API_KEY" ]]; then
    print_error "Cloudflare email and API key are required"
    show_usage
    exit 1
fi

echo -e "${CYAN}🔐 Setting up SSL certificates for $DOMAIN...${NC}"

# Check if Docker is running
if ! docker version >/dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi
print_status "Docker is running"

# Check if docker-compose.yml exists
if [[ ! -f "docker-compose.yml" ]]; then
    print_error "docker-compose.yml not found. Please run this script from the project root."
    exit 1
fi

# Create Cloudflare credentials file
print_info "Creating Cloudflare credentials file..."
cat > certbot/cloudflare.ini << EOF
dns_cloudflare_email = $CLOUDFLARE_EMAIL
dns_cloudflare_api_key = $CLOUDFLARE_API_KEY
EOF

# Set proper permissions
chmod 600 certbot/cloudflare.ini
print_status "Cloudflare credentials file created with proper permissions"

# Create certbot directories
print_info "Creating certbot directories..."
mkdir -p certbot/conf certbot/www

# Run certbot to get SSL certificate
print_info "Requesting SSL certificate from Let's Encrypt..."
print_warning "This may take a few minutes..."

if docker-compose run --rm certbot; then
    
    print_status "SSL certificate setup complete!"
    echo -e "${CYAN}🚀 You can now start the services with: docker-compose up -d${NC}"
    echo -e "${CYAN}🌐 Your email system will be available at: https://$DOMAIN${NC}"
else
    print_error "SSL certificate setup failed. Check the logs above."
    exit 1
fi

echo ""
echo -e "${CYAN}📋 Next steps:${NC}"
echo "1. Start services: docker-compose up -d"
echo "2. Test setup: ./test-docker.sh"
echo "3. Access your email system: https://$DOMAIN"
