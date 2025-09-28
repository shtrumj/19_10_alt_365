# 365 Email System Docker Management Script for Windows PowerShell

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("start", "stop", "restart", "status", "logs", "shell", "backup", "update", "clean")]
    [string]$Action,
    
    [string]$Service,
    [switch]$Follow,
    [switch]$Force
)

Write-Host "🔧 365 Email System Docker Management" -ForegroundColor Green

# Check if Docker is running
try {
    docker version | Out-Null
} catch {
    Write-Host "❌ Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check if docker-compose.yml exists
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "❌ docker-compose.yml not found. Please run this script from the project root." -ForegroundColor Red
    exit 1
}

switch ($Action) {
    "start" {
        Write-Host "🚀 Starting 365 Email System..." -ForegroundColor Yellow
        docker-compose up -d
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Services started successfully" -ForegroundColor Green
            Start-Sleep -Seconds 5
            docker-compose ps
        } else {
            Write-Host "❌ Failed to start services" -ForegroundColor Red
        }
    }
    
    "stop" {
        Write-Host "🛑 Stopping 365 Email System..." -ForegroundColor Yellow
        docker-compose down
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Services stopped successfully" -ForegroundColor Green
        } else {
            Write-Host "❌ Failed to stop services" -ForegroundColor Red
        }
    }
    
    "restart" {
        Write-Host "🔄 Restarting 365 Email System..." -ForegroundColor Yellow
        if ($Service) {
            docker-compose restart $Service
        } else {
            docker-compose restart
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Services restarted successfully" -ForegroundColor Green
        } else {
            Write-Host "❌ Failed to restart services" -ForegroundColor Red
        }
    }
    
    "status" {
        Write-Host "📊 Service Status:" -ForegroundColor Cyan
        docker-compose ps
        
        Write-Host "`n💾 Disk Usage:" -ForegroundColor Cyan
        docker system df
        
        Write-Host "`n🔍 Resource Usage:" -ForegroundColor Cyan
        docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
    }
    
    "logs" {
        if ($Service) {
            Write-Host "📋 Showing logs for $Service..." -ForegroundColor Yellow
            if ($Follow) {
                docker-compose logs -f $Service
            } else {
                docker-compose logs --tail=50 $Service
            }
        } else {
            Write-Host "📋 Showing logs for all services..." -ForegroundColor Yellow
            if ($Follow) {
                docker-compose logs -f
            } else {
                docker-compose logs --tail=50
            }
        }
    }
    
    "shell" {
        if (-not $Service) {
            $Service = "email-system"
        }
        Write-Host "🐚 Opening shell in $Service container..." -ForegroundColor Yellow
        docker-compose exec $Service /bin/bash
    }
    
    "backup" {
        Write-Host "💾 Creating backup..." -ForegroundColor Yellow
        
        $backupDir = "backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
        
        # Backup database
        try {
            docker-compose exec -T email-system cp /app/email_system.db /tmp/backup.db
            docker cp "365-email-system:/tmp/backup.db" "$backupDir\email_system.db"
            Write-Host "✅ Database backed up to $backupDir\email_system.db" -ForegroundColor Green
        } catch {
            Write-Host "⚠️  Could not backup database: $($_.Exception.Message)" -ForegroundColor Yellow
        }
        
        # Backup SSL certificates
        if (Test-Path "certbot\conf") {
            Copy-Item -Path "certbot\conf" -Destination "$backupDir\certbot_conf" -Recurse -Force
            Write-Host "✅ SSL certificates backed up to $backupDir\certbot_conf" -ForegroundColor Green
        }
        
        # Backup configuration
        Copy-Item -Path "docker-compose.yml" -Destination "$backupDir\" -Force
        Copy-Item -Path ".env" -Destination "$backupDir\" -Force -ErrorAction SilentlyContinue
        Write-Host "✅ Configuration files backed up" -ForegroundColor Green
        
        Write-Host "📁 Backup completed: $backupDir" -ForegroundColor Green
    }
    
    "update" {
        Write-Host "🔄 Updating 365 Email System..." -ForegroundColor Yellow
        
        # Pull latest images
        Write-Host "📥 Pulling latest images..." -ForegroundColor Cyan
        docker-compose pull
        
        # Rebuild and restart
        Write-Host "🔨 Rebuilding containers..." -ForegroundColor Cyan
        docker-compose up -d --build
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Update completed successfully" -ForegroundColor Green
        } else {
            Write-Host "❌ Update failed" -ForegroundColor Red
        }
    }
    
    "clean" {
        Write-Host "🧹 Cleaning up Docker resources..." -ForegroundColor Yellow
        
        if ($Force) {
            # Remove all containers, networks, and volumes
            docker-compose down -v --remove-orphans
            docker system prune -a -f
            Write-Host "✅ Deep clean completed" -ForegroundColor Green
        } else {
            # Remove only unused resources
            docker-compose down --remove-orphans
            docker system prune -f
            Write-Host "✅ Clean completed" -ForegroundColor Green
        }
    }
}

Write-Host "`n📋 Available commands:" -ForegroundColor Cyan
Write-Host "• Start: .\manage-docker.ps1 -Action start" -ForegroundColor White
Write-Host "• Stop: .\manage-docker.ps1 -Action stop" -ForegroundColor White
Write-Host "• Restart: .\manage-docker.ps1 -Action restart" -ForegroundColor White
Write-Host "• Status: .\manage-docker.ps1 -Action status" -ForegroundColor White
Write-Host "• Logs: .\manage-docker.ps1 -Action logs -Service email-system -Follow" -ForegroundColor White
Write-Host "• Shell: .\manage-docker.ps1 -Action shell -Service email-system" -ForegroundColor White
Write-Host "• Backup: .\manage-docker.ps1 -Action backup" -ForegroundColor White
Write-Host "• Update: .\manage-docker.ps1 -Action update" -ForegroundColor White
Write-Host "• Clean: .\manage-docker.ps1 -Action clean" -ForegroundColor White
