# 365 Email System SSL Setup Script for Windows PowerShell
# This script sets up SSL certificates using Cloudflare DNS challenge

param(
    [Parameter(Mandatory=$true)]
    [string]$CloudflareEmail,
    
    [Parameter(Mandatory=$true)]
    [string]$CloudflareApiKey,
    
    [string]$Domain = "owa.shtrum.com"
)

Write-Host "🔐 Setting up SSL certificates for $Domain..." -ForegroundColor Green

# Check if Docker is running
try {
    docker version | Out-Null
    Write-Host "✅ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check if docker-compose.yml exists
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "❌ docker-compose.yml not found. Please run this script from the project root." -ForegroundColor Red
    exit 1
}

# Create Cloudflare credentials file
Write-Host "📝 Creating Cloudflare credentials file..." -ForegroundColor Yellow
$cloudflareIni = @"
dns_cloudflare_email = $CloudflareEmail
dns_cloudflare_api_key = $CloudflareApiKey
"@

$cloudflareIni | Out-File -FilePath "certbot\cloudflare.ini" -Encoding UTF8

# Set proper permissions (Windows equivalent)
try {
    icacls "certbot\cloudflare.ini" /inheritance:r /grant:r "%USERNAME%:F" | Out-Null
    Write-Host "✅ Cloudflare credentials file created with proper permissions" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Could not set file permissions, but file was created" -ForegroundColor Yellow
}

# Create certbot directories
Write-Host "📁 Creating certbot directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path "certbot\conf" -Force | Out-Null
New-Item -ItemType Directory -Path "certbot\www" -Force | Out-Null

# Run certbot to get SSL certificate
Write-Host "🔒 Requesting SSL certificate from Let's Encrypt..." -ForegroundColor Yellow
Write-Host "This may take a few minutes..." -ForegroundColor Cyan

try {
    docker-compose run --rm certbot certonly `
        --dns-cloudflare `
        --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini `
        --email $CloudflareEmail `
        --agree-tos `
        --no-eff-email `
        -d $Domain

    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ SSL certificate setup complete!" -ForegroundColor Green
        Write-Host "🚀 You can now start the services with: docker-compose up -d" -ForegroundColor Cyan
        Write-Host "🌐 Your email system will be available at: https://$Domain" -ForegroundColor Cyan
    } else {
        Write-Host "❌ SSL certificate setup failed. Check the logs above." -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Error running certbot: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`n📋 Next steps:" -ForegroundColor Cyan
Write-Host "1. Start services: docker-compose up -d" -ForegroundColor White
Write-Host "2. Test setup: .\test-docker.ps1" -ForegroundColor White
Write-Host "3. Access your email system: https://$Domain" -ForegroundColor White
