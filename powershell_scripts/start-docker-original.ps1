# 365 Email System Docker Startup Script for Windows

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
    Copy-Item "env.example" ".env"
    Write-Host "📝 Please edit .env file with your configuration before continuing." -ForegroundColor Yellow
    Write-Host "Press any key to continue after editing .env file..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

# Build and start services
Write-Host "🔨 Building Docker images..." -ForegroundColor Yellow
docker-compose build

Write-Host "🚀 Starting services..." -ForegroundColor Yellow
docker-compose up -d

# Wait for services to start
Write-Host "⏳ Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check service status
Write-Host "📊 Service Status:" -ForegroundColor Cyan
docker-compose ps

# Test health endpoint
Write-Host "🏥 Testing health endpoint..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8001/health" -TimeoutSec 10
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Email system is healthy" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Email system responded with status: $($response.StatusCode)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Email system health check failed: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "🎉 Setup complete!" -ForegroundColor Green
Write-Host "📧 Web Interface: http://localhost:8001/owa" -ForegroundColor Cyan
Write-Host "📚 API Docs: http://localhost:8001/docs" -ForegroundColor Cyan
Write-Host "🔧 To view logs: docker-compose logs -f" -ForegroundColor Cyan
