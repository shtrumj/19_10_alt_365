# 365 Email System SSL Setup Script for Windows
# This script sets up SSL certificates using Cloudflare DNS challenge

param(
    [string]$CloudflareEmail,
    [string]$CloudflareApiKey
)

Write-Host "🔐 Setting up SSL certificates for owa.shtrum.com..." -ForegroundColor Green

# Check if environment variables are set
if (-not $CloudflareEmail -or -not $CloudflareApiKey) {
    Write-Host "❌ Error: CloudflareEmail and CloudflareApiKey parameters are required" -ForegroundColor Red
    Write-Host "Usage: .\setup-ssl.ps1 -CloudflareEmail 'your-email@example.com' -CloudflareApiKey 'your-api-key'"
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
icacls "certbot\cloudflare.ini" /inheritance:r /grant:r "%USERNAME%:F"

# Create certbot directories
New-Item -ItemType Directory -Path "certbot\conf" -Force | Out-Null
New-Item -ItemType Directory -Path "certbot\www" -Force | Out-Null

# Run certbot to get SSL certificate
Write-Host "🔒 Requesting SSL certificate from Let's Encrypt..." -ForegroundColor Yellow
docker-compose run --rm certbot certonly `
    --dns-cloudflare `
    --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini `
    --email $CloudflareEmail `
    --agree-tos `
    --no-eff-email `
    -d owa.shtrum.com

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ SSL certificate setup complete!" -ForegroundColor Green
    Write-Host "🚀 You can now start the services with: docker-compose up -d" -ForegroundColor Cyan
} else {
    Write-Host "❌ SSL certificate setup failed. Check the logs above." -ForegroundColor Red
    exit 1
}
