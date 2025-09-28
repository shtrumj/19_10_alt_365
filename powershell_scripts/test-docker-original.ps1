# 365 Email System Docker Test Script

Write-Host "🧪 Testing 365 Email System Docker Setup..." -ForegroundColor Green

# Test 1: Check if containers are running
Write-Host "`n1. Checking container status..." -ForegroundColor Cyan
$containers = docker-compose ps --services
foreach ($container in $containers) {
    $status = docker-compose ps -q $container
    if ($status) {
        Write-Host "✅ $container is running" -ForegroundColor Green
    } else {
        Write-Host "❌ $container is not running" -ForegroundColor Red
    }
}

# Test 2: Check HTTP endpoints
Write-Host "`n2. Testing HTTP endpoints..." -ForegroundColor Cyan

$endpoints = @(
    @{Url="http://localhost:8001/health"; Name="Health Check"},
    @{Url="http://localhost:8001/"; Name="Root Endpoint"},
    @{Url="http://localhost:8001/owa/"; Name="OWA Interface"}
)

foreach ($endpoint in $endpoints) {
    try {
        $response = Invoke-WebRequest -Uri $endpoint.Url -TimeoutSec 5
        if ($response.StatusCode -eq 200 -or $response.StatusCode -eq 302) {
            Write-Host "✅ $($endpoint.Name): HTTP $($response.StatusCode)" -ForegroundColor Green
        } else {
            Write-Host "⚠️  $($endpoint.Name): HTTP $($response.StatusCode)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "❌ $($endpoint.Name): $($_.Exception.Message)" -ForegroundColor Red
    }
}

# Test 3: Check SSL certificate (if available)
Write-Host "`n3. Checking SSL certificate..." -ForegroundColor Cyan
if (Test-Path "certbot\conf\live\owa.shtrum.com\fullchain.pem") {
    Write-Host "✅ SSL certificate found" -ForegroundColor Green
    
    # Check certificate expiry
    try {
        $cert = Get-Content "certbot\conf\live\owa.shtrum.com\fullchain.pem" -Raw
        Write-Host "📜 Certificate details available" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  Could not read certificate details" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠️  SSL certificate not found. Run setup-ssl.ps1 first." -ForegroundColor Yellow
}

# Test 4: Check logs for errors
Write-Host "`n4. Checking for errors in logs..." -ForegroundColor Cyan
$services = @("email-system", "nginx", "certbot")
foreach ($service in $services) {
    try {
        $logs = docker-compose logs --tail=10 $service 2>&1
        if ($logs -match "error|Error|ERROR|failed|Failed|FAILED") {
            Write-Host "⚠️  $service has errors in logs" -ForegroundColor Yellow
        } else {
            Write-Host "✅ $service logs look clean" -ForegroundColor Green
        }
    } catch {
        Write-Host "❌ Could not check logs for $service" -ForegroundColor Red
    }
}

# Test 5: Check port accessibility
Write-Host "`n5. Checking port accessibility..." -ForegroundColor Cyan
$ports = @(80, 443, 8001)
foreach ($port in $ports) {
    try {
        $connection = Test-NetConnection -ComputerName "localhost" -Port $port -WarningAction SilentlyContinue
        if ($connection.TcpTestSucceeded) {
            Write-Host "✅ Port $port is accessible" -ForegroundColor Green
        } else {
            Write-Host "❌ Port $port is not accessible" -ForegroundColor Red
        }
    } catch {
        Write-Host "⚠️  Could not test port $port" -ForegroundColor Yellow
    }
}

Write-Host "`n🎉 Testing complete!" -ForegroundColor Green
Write-Host "📊 For detailed logs: docker-compose logs -f" -ForegroundColor Cyan
Write-Host "🔧 For service management: docker-compose ps" -ForegroundColor Cyan
