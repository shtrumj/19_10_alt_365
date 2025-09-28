#!/bin/bash

# 365 Email System Docker Startup Script for Mac/Linux

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values
BUILD=false
DETACH=true

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
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -b, --build     Build images before starting"
    echo "  -f, --foreground Run in foreground (don't detach)"
    echo "  -h, --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Start in background"
    echo "  $0 --build           # Build and start in background"
    echo "  $0 --foreground      # Start in foreground"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -b|--build)
            BUILD=true
            shift
            ;;
        -f|--foreground)
            DETACH=false
            shift
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

echo -e "${CYAN}🚀 Starting 365 Email System with Docker...${NC}"

# Check if Docker is running
if ! docker version >/dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi
print_status "Docker is running"

# Check if .env file exists
if [[ ! -f ".env" ]]; then
    print_warning ".env file not found. Creating from example..."
    if [[ -f "env.example" ]]; then
        cp env.example .env
        print_info "Please edit .env file with your configuration before continuing."
        read -p "Press Enter to continue after editing .env file..."
    else
        print_error "env.example file not found. Please create a .env file manually."
        exit 1
    fi
fi

# Build images if requested
if [[ "$BUILD" == "true" ]]; then
    print_info "Building Docker images..."
    if docker-compose build; then
        print_status "Docker images built successfully"
    else
        print_error "Docker build failed"
        exit 1
    fi
fi

# Start services
print_info "Starting services..."
if [[ "$DETACH" == "true" ]]; then
    docker-compose up -d
else
    docker-compose up
fi

if [[ $? -ne 0 ]]; then
    print_error "Failed to start services"
    exit 1
fi

# Wait for services to start
print_info "Waiting for services to start..."
sleep 15

# Check service status
echo -e "\n${CYAN}📊 Service Status:${NC}"
docker-compose ps

# Test health endpoint
echo -e "\n${CYAN}🏥 Testing health endpoint...${NC}"
MAX_RETRIES=5
RETRY_COUNT=0

while [[ $RETRY_COUNT -lt $MAX_RETRIES ]]; do
    if curl -f -s http://localhost:8001/health >/dev/null 2>&1; then
        print_status "Email system is healthy"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [[ $RETRY_COUNT -lt $MAX_RETRIES ]]; then
            print_warning "Retrying health check ($RETRY_COUNT/$MAX_RETRIES)..."
            sleep 5
        else
            print_error "Email system health check failed after $MAX_RETRIES attempts"
            print_info "Check logs with: docker-compose logs email-system"
        fi
    fi
done

# Display access information
echo -e "\n${GREEN}🎉 Setup complete!${NC}"
echo -e "${CYAN}📧 Web Interface: http://localhost:8001/owa${NC}"
echo -e "${CYAN}📚 API Docs: http://localhost:8001/docs${NC}"
echo -e "${CYAN}🔧 To view logs: docker-compose logs -f${NC}"
echo -e "${CYAN}🛑 To stop services: docker-compose down${NC}"

# Check if SSL certificate exists
if [[ -f "certbot/conf/live/owa.shtrum.com/fullchain.pem" ]]; then
    print_status "SSL certificate found - HTTPS should be available"
else
    print_warning "SSL certificate not found. Run setup-ssl.sh to configure HTTPS"
fi
