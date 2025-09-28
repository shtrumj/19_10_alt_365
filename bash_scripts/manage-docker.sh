#!/bin/bash

# 365 Email System Docker Management Script for Mac/Linux

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

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
    echo "Usage: $0 <action> [options]"
    echo ""
    echo "Actions:"
    echo "  start       Start all services"
    echo "  stop        Stop all services"
    echo "  restart     Restart all services"
    echo "  status      Show service status"
    echo "  logs        Show service logs"
    echo "  shell       Open shell in container"
    echo "  backup      Create backup"
    echo "  update      Update services"
    echo "  clean       Clean up Docker resources"
    echo ""
    echo "Options:"
    echo "  -s, --service <name>    Target specific service"
    echo "  -f, --follow            Follow logs (for logs action)"
    echo "  --force                 Force operation (for clean action)"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 logs -s email-system -f"
    echo "  $0 shell -s email-system"
    echo "  $0 backup"
    echo "  $0 clean --force"
}

# Parse command line arguments
ACTION=""
SERVICE=""
FOLLOW=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        start|stop|restart|status|logs|shell|backup|update|clean)
            ACTION="$1"
            shift
            ;;
        -s|--service)
            SERVICE="$2"
            shift 2
            ;;
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        --force)
            FORCE=true
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

# Check if action is provided
if [[ -z "$ACTION" ]]; then
    print_error "Action is required"
    show_usage
    exit 1
fi

# Check if Docker is running
if ! docker version >/dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi

# Check if docker-compose.yml exists
if [[ ! -f "docker-compose.yml" ]]; then
    print_error "docker-compose.yml not found. Please run this script from the project root."
    exit 1
fi

echo -e "${CYAN}🔧 365 Email System Docker Management${NC}"

case "$ACTION" in
    "start")
        print_info "Starting 365 Email System..."
        if docker-compose up -d; then
            print_status "Services started successfully"
            sleep 5
            docker-compose ps
        else
            print_error "Failed to start services"
        fi
        ;;
    
    "stop")
        print_info "Stopping 365 Email System..."
        if docker-compose down; then
            print_status "Services stopped successfully"
        else
            print_error "Failed to stop services"
        fi
        ;;
    
    "restart")
        print_info "Restarting 365 Email System..."
        if [[ -n "$SERVICE" ]]; then
            docker-compose restart "$SERVICE"
        else
            docker-compose restart
        fi
        
        if [[ $? -eq 0 ]]; then
            print_status "Services restarted successfully"
        else
            print_error "Failed to restart services"
        fi
        ;;
    
    "status")
        print_info "Service Status:"
        docker-compose ps
        
        echo -e "\n${CYAN}💾 Disk Usage:${NC}"
        docker system df
        
        echo -e "\n${CYAN}🔍 Resource Usage:${NC}"
        docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
        ;;
    
    "logs")
        if [[ -n "$SERVICE" ]]; then
            print_info "Showing logs for $SERVICE..."
            if [[ "$FOLLOW" == "true" ]]; then
                docker-compose logs -f "$SERVICE"
            else
                docker-compose logs --tail=50 "$SERVICE"
            fi
        else
            print_info "Showing logs for all services..."
            if [[ "$FOLLOW" == "true" ]]; then
                docker-compose logs -f
            else
                docker-compose logs --tail=50
            fi
        fi
        ;;
    
    "shell")
        if [[ -z "$SERVICE" ]]; then
            SERVICE="email-system"
        fi
        print_info "Opening shell in $SERVICE container..."
        docker-compose exec "$SERVICE" /bin/bash
        ;;
    
    "backup")
        print_info "Creating backup..."
        
        BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        
        # Backup database
        if docker-compose exec -T email-system cp /app/email_system.db /tmp/backup.db && \
           docker cp "365-email-system:/tmp/backup.db" "$BACKUP_DIR/email_system.db"; then
            print_status "Database backed up to $BACKUP_DIR/email_system.db"
        else
            print_warning "Could not backup database"
        fi
        
        # Backup SSL certificates
        if [[ -d "certbot/conf" ]]; then
            cp -r certbot/conf "$BACKUP_DIR/certbot_conf"
            print_status "SSL certificates backed up to $BACKUP_DIR/certbot_conf"
        fi
        
        # Backup configuration
        cp docker-compose.yml "$BACKUP_DIR/"
        [[ -f ".env" ]] && cp .env "$BACKUP_DIR/"
        print_status "Configuration files backed up"
        
        print_status "Backup completed: $BACKUP_DIR"
        ;;
    
    "update")
        print_info "Updating 365 Email System..."
        
        # Pull latest images
        print_info "Pulling latest images..."
        docker-compose pull
        
        # Rebuild and restart
        print_info "Rebuilding containers..."
        if docker-compose up -d --build; then
            print_status "Update completed successfully"
        else
            print_error "Update failed"
        fi
        ;;
    
    "clean")
        print_info "Cleaning up Docker resources..."
        
        if [[ "$FORCE" == "true" ]]; then
            # Remove all containers, networks, and volumes
            docker-compose down -v --remove-orphans
            docker system prune -a -f
            print_status "Deep clean completed"
        else
            # Remove only unused resources
            docker-compose down --remove-orphans
            docker system prune -f
            print_status "Clean completed"
        fi
        ;;
esac

echo -e "\n${CYAN}📋 Available commands:${NC}"
echo "• Start: $0 start"
echo "• Stop: $0 stop"
echo "• Restart: $0 restart"
echo "• Status: $0 status"
echo "• Logs: $0 logs -s email-system -f"
echo "• Shell: $0 shell -s email-system"
echo "• Backup: $0 backup"
echo "• Update: $0 update"
echo "• Clean: $0 clean"
