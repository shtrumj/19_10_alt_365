# 365 Email System Docker Startup Script for Windows PowerShell

param(
    [switch]$Build,
    [switch]$Detach = $true
)

Write-Host "🚀 Starting 365 Email System with Docker..." -ForegroundColor Green

# Check if Docker is running
try {
    docker version | Out-Null
    Write-Host "✅ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  .env file not found. Creating from example..." -ForegroundColor Yellow
    if (Test-Path "env.example") {
        Copy-Item "env.example" ".env"
        Write-Host "📝 Please edit .env file with your configuration before continuing." -ForegroundColor Yellow
        Write-Host "Press any key to continue after editing .env file..." -ForegroundColor Cyan
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    } else {
        Write-Host "❌ env.example file not found. Please create a .env file manually." -ForegroundColor Red
        exit 1
    }
}

# Build images if requested
if ($Build) {
    Write-Host "🔨 Building Docker images..." -ForegroundColor Yellow
    docker-compose build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Docker build failed" -ForegroundColor Red
        exit 1
    }
}

# Start services
Write-Host "🚀 Starting services..." -ForegroundColor Yellow
if ($Detach) {
    docker-compose up -d
} else {
    docker-compose up
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to start services" -ForegroundColor Red
    exit 1
}

# Wait for services to start
Write-Host "⏳ Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# Check service status
Write-Host "`n📊 Service Status:" -ForegroundColor Cyan
docker-compose ps

# Test health endpoint
Write-Host "`n🏥 Testing health endpoint..." -ForegroundColor Yellow
$maxRetries = 5
$retryCount = 0

do {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8001/health" -TimeoutSec 10
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ Email system is healthy" -ForegroundColor Green
            break
        } else {
            Write-Host "⚠️  Email system responded with status: $($response.StatusCode)" -ForegroundColor Yellow
        }
    } catch {
        $retryCount++
        if ($retryCount -lt $maxRetries) {
            Write-Host "⏳ Retrying health check ($retryCount/$maxRetries)..." -ForegroundColor Yellow
            Start-Sleep -Seconds 5
        } else {
            Write-Host "❌ Email system health check failed after $maxRetries attempts" -ForegroundColor Red
            Write-Host "Check logs with: docker-compose logs email-system" -ForegroundColor Cyan
        }
    }
} while ($retryCount -lt $maxRetries)

# Display access information
Write-Host "`n🎉 Setup complete!" -ForegroundColor Green
Write-Host "📧 Web Interface: http://localhost:8001/owa" -ForegroundColor Cyan
Write-Host "📚 API Docs: http://localhost:8001/docs" -ForegroundColor Cyan
Write-Host "🔧 To view logs: docker-compose logs -f" -ForegroundColor Cyan
Write-Host "🛑 To stop services: docker-compose down" -ForegroundColor Cyan

# Check if SSL certificate exists
if (Test-Path "certbot\conf\live\owa.shtrum.com\fullchain.pem") {
    Write-Host "🔒 SSL certificate found - HTTPS should be available" -ForegroundColor Green
} else {
    Write-Host "⚠️  SSL certificate not found. Run setup-ssl.ps1 to configure HTTPS" -ForegroundColor Yellow
}
