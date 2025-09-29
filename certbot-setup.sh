#!/bin/sh

set -e

# Ensure letsencrypt directory exists
mkdir -p /etc/letsencrypt

# Create Cloudflare credentials file from environment variables
# Prefer API token if provided; otherwise use email + global API key
if [ -n "$CLOUDFLARE_API_TOKEN" ]; then
  echo "dns_cloudflare_api_token = $CLOUDFLARE_API_TOKEN" > /etc/letsencrypt/cloudflare.ini
else
  if [ -z "$CLOUDFLARE_EMAIL" ] || [ -z "$CLOUDFLARE_API_KEY" ]; then
    echo "CLOUDFLARE_EMAIL and CLOUDFLARE_API_KEY (or CLOUDFLARE_API_TOKEN) must be set" >&2
    exit 1
  fi
  {
    echo "dns_cloudflare_email = $CLOUDFLARE_EMAIL"
    echo "dns_cloudflare_api_key = $CLOUDFLARE_API_KEY"
  } > /etc/letsencrypt/cloudflare.ini
fi

chmod 600 /etc/letsencrypt/cloudflare.ini

# Domain to issue certificate for
DOMAIN_NAME=${DOMAIN:-owa.shtrum.com}
ALT_NAMES=${ALT_NAMES:-autodiscover.shtrum.com,mail.shtrum.com}
PROPAGATION_SECONDS=${PROPAGATION_SECONDS:-180}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@shtrum.com}

# Run certbot using the Cloudflare DNS plugin
certbot certonly --expand \
  --non-interactive \
  --agree-tos \
  --email "$ADMIN_EMAIL" \
  --dns-cloudflare \
  --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \
  --dns-cloudflare-propagation-seconds "$PROPAGATION_SECONDS" \
  -d "$DOMAIN_NAME" $(printf ' -d %s' $(echo "$ALT_NAMES" | tr ',' ' '))

echo "Certificate request finished for $DOMAIN_NAME (SANs: $ALT_NAMES)"
