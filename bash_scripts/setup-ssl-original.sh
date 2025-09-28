#!/bin/bash

# 365 Email System SSL Setup Script
# This script sets up SSL certificates using Cloudflare DNS challenge

set -e

echo "🔐 Setting up SSL certificates for owa.shtrum.com..."

# Check if environment variables are set
if [ -z "$CLOUDFLARE_EMAIL" ] || [ -z "$CLOUDFLARE_API_KEY" ]; then
    echo "❌ Error: CLOUDFLARE_EMAIL and CLOUDFLARE_API_KEY must be set"
    echo "Please set these environment variables or create a .env file"
    exit 1
fi

# Create Cloudflare credentials file
echo "📝 Creating Cloudflare credentials file..."
cat > certbot/cloudflare.ini << EOF
dns_cloudflare_email = $CLOUDFLARE_EMAIL
dns_cloudflare_api_key = $CLOUDFLARE_API_KEY
EOF

# Set proper permissions
chmod 600 certbot/cloudflare.ini

# Create certbot directories
mkdir -p certbot/conf certbot/www

# Run certbot to get SSL certificate
echo "🔒 Requesting SSL certificate from Let's Encrypt..."
docker-compose run --rm certbot certonly \
    --dns-cloudflare \
    --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \
    --email $CLOUDFLARE_EMAIL \
    --agree-tos \
    --no-eff-email \
    -d owa.shtrum.com

echo "✅ SSL certificate setup complete!"
echo "🚀 You can now start the services with: docker-compose up -d"
