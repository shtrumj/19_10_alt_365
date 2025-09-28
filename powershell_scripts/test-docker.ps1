# 365 Email System Docker Test Script for Windows PowerShell

param(
    [switch]$Verbose,
    [switch]$Quick
)

Write-Host "🧪 Testing 365 Email System Docker Setup..." -ForegroundColor Green

# Test 1: Check if containers are running
Write-Host "`n1. Checking container status..." -ForegroundColor Cyan
$containers = docker-compose ps --services
$allRunning = $true

foreach ($container in $containers) {
    $status = docker-compose ps -q $container
    if ($status) {
        $containerStatus = docker-compose ps --format "table {{.Name}}\t{{.Status}}" | Select-String $container
        if ($containerStatus -match "Up") {
            Write-Host "✅ $container is running" -ForegroundColor Green
        } else {
            Write-Host "⚠️  $container is created but not running" -ForegroundColor Yellow
            $allRunning = $false
        }
    } else {
        Write-Host "❌ $container is not running" -ForegroundColor Red
        $allRunning = $false
    }
}

if (-not $allRunning) {
    Write-Host "⚠️  Some containers are not running. Check with: docker-compose ps" -ForegroundColor Yellow
}

# Test 2: Check HTTP endpoints
Write-Host "`n2. Testing HTTP endpoints..." -ForegroundColor Cyan

$endpoints = @(
    @{Url="http://localhost:8001/health"; Name="Health Check"; ExpectedStatus=200},
    @{Url="http://localhost:8001/"; Name="Root Endpoint"; ExpectedStatus=200},
    @{Url="http://localhost:8001/owa/"; Name="OWA Interface"; ExpectedStatus=302}
)

$endpointsWorking = 0
foreach ($endpoint in $endpoints) {
    try {
        $response = Invoke-WebRequest -Uri $endpoint.Url -TimeoutSec 10
        if ($response.StatusCode -eq $endpoint.ExpectedStatus) {
            Write-Host "✅ $($endpoint.Name): HTTP $($response.StatusCode)" -ForegroundColor Green
            $endpointsWorking++
        } else {
            Write-Host "⚠️  $($endpoint.Name): HTTP $($response.StatusCode) (expected $($endpoint.ExpectedStatus))" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "❌ $($endpoint.Name): $($_.Exception.Message)" -ForegroundColor Red
    }
}

# Test 3: Check SSL certificate (if available)
Write-Host "`n3. Checking SSL certificate..." -ForegroundColor Cyan
$sslCertPath = "certbot\conf\live\owa.shtrum.com\fullchain.pem"
if (Test-Path $sslCertPath) {
    Write-Host "✅ SSL certificate found" -ForegroundColor Green
    
    # Check certificate expiry
    try {
        $certContent = Get-Content $sslCertPath -Raw
        if ($certContent -match "BEGIN CERTIFICATE") {
            Write-Host "📜 Certificate appears valid" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Certificate file exists but may be invalid" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "⚠️  Could not read certificate details" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠️  SSL certificate not found. Run setup-ssl.ps1 first." -ForegroundColor Yellow
}

# Test 4: Check logs for errors
Write-Host "`n4. Checking for errors in logs..." -ForegroundColor Cyan
$services = @("email-system", "nginx", "certbot")
$errorCount = 0

foreach ($service in $services) {
    try {
        $logs = docker-compose logs --tail=20 $service 2>&1
        $errorLines = $logs | Where-Object { $_ -match "error|Error|ERROR|failed|Failed|FAILED|exception|Exception" }
        
        if ($errorLines) {
            Write-Host "⚠️  $service has errors in logs ($($errorLines.Count) lines)" -ForegroundColor Yellow
            if ($Verbose) {
                $errorLines | ForEach-Object { Write-Host "   $_" -ForegroundColor DarkYellow }
            }
            $errorCount++
        } else {
            Write-Host "✅ $service logs look clean" -ForegroundColor Green
        }
    } catch {
        Write-Host "❌ Could not check logs for $service" -ForegroundColor Red
        $errorCount++
    }
}

# Test 5: Check port accessibility
Write-Host "`n5. Checking port accessibility..." -ForegroundColor Cyan
$ports = @(80, 443, 8001)
$portsOpen = 0

foreach ($port in $ports) {
    try {
        $connection = Test-NetConnection -ComputerName "localhost" -Port $port -WarningAction SilentlyContinue
        if ($connection.TcpTestSucceeded) {
            Write-Host "✅ Port $port is accessible" -ForegroundColor Green
            $portsOpen++
        } else {
            Write-Host "❌ Port $port is not accessible" -ForegroundColor Red
        }
    } catch {
        Write-Host "⚠️  Could not test port $port" -ForegroundColor Yellow
    }
}

# Test 6: Database connectivity (if not quick mode)
if (-not $Quick) {
    Write-Host "`n6. Testing database connectivity..." -ForegroundColor Cyan
    try {
        $dbTest = docker-compose exec -T email-system python -c "from app.database import engine; print('Database connection successful')" 2>&1
        if ($dbTest -match "Database connection successful") {
            Write-Host "✅ Database connection successful" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Database connection test inconclusive" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "⚠️  Could not test database connection" -ForegroundColor Yellow
    }
}

# Summary
Write-Host "`n📊 Test Summary:" -ForegroundColor Cyan
Write-Host "Containers: $($allRunning ? 'All Running' : 'Some Issues')" -ForegroundColor $(if($allRunning) {'Green'} else {'Yellow'})
Write-Host "Endpoints: $endpointsWorking/$($endpoints.Count) working" -ForegroundColor $(if($endpointsWorking -eq $endpoints.Count) {'Green'} else {'Yellow'})
Write-Host "Ports: $portsOpen/$($ports.Count) accessible" -ForegroundColor $(if($portsOpen -eq $ports.Count) {'Green'} else {'Yellow'})
Write-Host "Log Errors: $errorCount services with issues" -ForegroundColor $(if($errorCount -eq 0) {'Green'} else {'Yellow'})

if ($allRunning -and $endpointsWorking -eq $endpoints.Count -and $portsOpen -eq $ports.Count -and $errorCount -eq 0) {
    Write-Host "`n🎉 All tests passed! Your email system is ready." -ForegroundColor Green
} else {
    Write-Host "`n⚠️  Some issues detected. Check the details above." -ForegroundColor Yellow
}

Write-Host "`n📋 Useful commands:" -ForegroundColor Cyan
Write-Host "• View logs: docker-compose logs -f" -ForegroundColor White
Write-Host "• Check status: docker-compose ps" -ForegroundColor White
Write-Host "• Restart services: docker-compose restart" -ForegroundColor White
Write-Host "• Stop services: docker-compose down" -ForegroundColor White
