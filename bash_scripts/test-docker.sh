#!/bin/bash

# 365 Email System Docker Test Script for Mac/Linux

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values
VERBOSE=false
QUICK=false

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
    echo "  -v, --verbose   Show verbose output"
    echo "  -q, --quick     Run quick tests only"
    echo "  -h, --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Run all tests"
    echo "  $0 --verbose         # Run tests with verbose output"
    echo "  $0 --quick           # Run quick tests only"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -q|--quick)
            QUICK=true
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

echo -e "${CYAN}🧪 Testing 365 Email System Docker Setup...${NC}"

# Test 1: Check if containers are running
echo -e "\n${CYAN}1. Checking container status...${NC}"
CONTAINERS=$(docker-compose ps --services)
ALL_RUNNING=true

for container in $CONTAINERS; do
    if docker-compose ps -q "$container" >/dev/null 2>&1; then
        STATUS=$(docker-compose ps --format "table {{.Name}}\t{{.Status}}" | grep "$container" | awk '{print $2}')
        if [[ "$STATUS" == *"Up"* ]]; then
            print_status "$container is running"
        else
            print_warning "$container is created but not running"
            ALL_RUNNING=false
        fi
    else
        print_error "$container is not running"
        ALL_RUNNING=false
    fi
done

if [[ "$ALL_RUNNING" != "true" ]]; then
    print_warning "Some containers are not running. Check with: docker-compose ps"
fi

# Test 2: Check HTTP endpoints
echo -e "\n${CYAN}2. Testing HTTP endpoints...${NC}"

declare -a endpoints=(
    "http://localhost:8001/health:Health Check:200"
    "http://localhost:8001/:Root Endpoint:200"
    "http://localhost:8001/owa/:OWA Interface:302"
)

ENDPOINTS_WORKING=0
for endpoint in "${endpoints[@]}"; do
    IFS=':' read -r url name expected_status <<< "$endpoint"
    
    if response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null); then
        if [[ "$response" == "$expected_status" ]]; then
            print_status "$name: HTTP $response"
            ENDPOINTS_WORKING=$((ENDPOINTS_WORKING + 1))
        else
            print_warning "$name: HTTP $response (expected $expected_status)"
        fi
    else
        print_error "$name: Connection failed"
    fi
done

# Test 3: Check SSL certificate (if available)
echo -e "\n${CYAN}3. Checking SSL certificate...${NC}"
SSL_CERT_PATH="certbot/conf/live/owa.shtrum.com/fullchain.pem"

if [[ -f "$SSL_CERT_PATH" ]]; then
    print_status "SSL certificate found"
    
    # Check certificate expiry
    if command -v openssl >/dev/null 2>&1; then
        if openssl x509 -in "$SSL_CERT_PATH" -text -noout >/dev/null 2>&1; then
            print_status "Certificate appears valid"
        else
            print_warning "Certificate file exists but may be invalid"
        fi
    else
        print_info "OpenSSL not available, skipping certificate validation"
    fi
else
    print_warning "SSL certificate not found. Run setup-ssl.sh first."
fi

# Test 4: Check logs for errors
echo -e "\n${CYAN}4. Checking for errors in logs...${NC}"
services=("email-system" "nginx" "certbot")
ERROR_COUNT=0

for service in "${services[@]}"; do
    if logs=$(docker-compose logs --tail=20 "$service" 2>&1); then
        error_lines=$(echo "$logs" | grep -i "error\|failed\|exception" | wc -l)
        
        if [[ $error_lines -gt 0 ]]; then
            print_warning "$service has errors in logs ($error_lines lines)"
            if [[ "$VERBOSE" == "true" ]]; then
                echo "$logs" | grep -i "error\|failed\|exception" | while read -r line; do
                    echo -e "${YELLOW}   $line${NC}"
                done
            fi
            ERROR_COUNT=$((ERROR_COUNT + 1))
        else
            print_status "$service logs look clean"
        fi
    else
        print_error "Could not check logs for $service"
        ERROR_COUNT=$((ERROR_COUNT + 1))
    fi
done

# Test 5: Check port accessibility
echo -e "\n${CYAN}5. Checking port accessibility...${NC}"
ports=(80 443 8001)
PORTS_OPEN=0

for port in "${ports[@]}"; do
    if nc -z localhost "$port" 2>/dev/null; then
        print_status "Port $port is accessible"
        PORTS_OPEN=$((PORTS_OPEN + 1))
    else
        print_error "Port $port is not accessible"
    fi
done

# Test 6: Database connectivity (if not quick mode)
if [[ "$QUICK" != "true" ]]; then
    echo -e "\n${CYAN}6. Testing database connectivity...${NC}"
    if docker-compose exec -T email-system python -c "from app.database import engine; print('Database connection successful')" 2>/dev/null | grep -q "Database connection successful"; then
        print_status "Database connection successful"
    else
        print_warning "Database connection test inconclusive"
    fi
fi

# Summary
echo -e "\n${CYAN}📊 Test Summary:${NC}"
echo "Containers: $([ "$ALL_RUNNING" == "true" ] && echo -e "${GREEN}All Running${NC}" || echo -e "${YELLOW}Some Issues${NC}")"
echo "Endpoints: $ENDPOINTS_WORKING/${#endpoints[@]} working"
echo "Ports: $PORTS_OPEN/${#ports[@]} accessible"
echo "Log Errors: $ERROR_COUNT services with issues"

if [[ "$ALL_RUNNING" == "true" && $ENDPOINTS_WORKING -eq ${#endpoints[@]} && $PORTS_OPEN -eq ${#ports[@]} && $ERROR_COUNT -eq 0 ]]; then
    echo -e "\n${GREEN}🎉 All tests passed! Your email system is ready.${NC}"
else
    echo -e "\n${YELLOW}⚠️  Some issues detected. Check the details above.${NC}"
fi

echo -e "\n${CYAN}📋 Useful commands:${NC}"
echo "• View logs: docker-compose logs -f"
echo "• Check status: docker-compose ps"
echo "• Restart services: docker-compose restart"
echo "• Stop services: docker-compose down"
