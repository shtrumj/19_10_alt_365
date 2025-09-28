#!/bin/bash

# Create credentials file
echo 'dns_cloudflare_api_token = xH0xDfYXM0zjsvZIuGtFB4ih-sDwOUrJFIt2I-iz' > /etc/letsencrypt/cloudflare.ini
chmod 600 /etc/letsencrypt/cloudflare.ini

# Run certbot
certonly --dns-cloudflare --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini --email admin@shtrum.com --agree-tos --no-eff-email -d owa.shtrum.com
