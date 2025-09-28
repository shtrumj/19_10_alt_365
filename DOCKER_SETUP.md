# 365 Email System - Docker Setup

This guide will help you deploy the 365 Email System using Docker with Nginx reverse proxy and SSL certificates.

## Prerequisites

- Docker and Docker Compose installed
- Domain `owa.shtrum.com` pointing to your server
- Cloudflare account with API access
- Server with ports 80 and 443 open

## Quick Start

### 1. Environment Setup

Copy the environment example file:
```bash
cp env.example .env
```

Edit `.env` with your configuration:
```bash
# Security
SECRET_KEY=your-very-long-and-secure-secret-key-here

# Cloudflare API (for SSL certificates)
CLOUDFLARE_EMAIL=your-email@example.com
CLOUDFLARE_API_KEY=your-cloudflare-api-key

# Domain
DOMAIN=owa.shtrum.com
```

### 2. Cloudflare API Setup

1. Log in to your Cloudflare dashboard
2. Go to "My Profile" → "API Tokens"
3. Create a new token with:
   - Zone: `shtrum.com` (Read)
   - Zone Resources: Include all zones
   - Additional permissions: DNS:Edit
4. Copy the API key to your `.env` file

### 3. SSL Certificate Setup

Run the SSL setup script:
```bash
./setup-ssl.sh
```

This will:
- Create Cloudflare credentials file
- Request SSL certificate from Let's Encrypt
- Set up proper file permissions

### 4. Start Services

Start all services:
```bash
docker-compose up -d
```

Check service status:
```bash
docker-compose ps
```

### 5. Access Your Email System

- **Web Interface**: https://owa.shtrum.com
- **API Documentation**: https://owa.shtrum.com/docs
- **Health Check**: https://owa.shtrum.com/health

## Service Architecture

```
Internet → Nginx (Port 80/443) → 365 Email System (Port 8001)
                ↓
            SSL Termination
                ↓
        Cloudflare DNS Challenge
```

## Services

### 365 Email System
- **Container**: `365-email-system`
- **Port**: 8001 (internal)
- **Features**: FastAPI, SQLite, SMTP server
- **Health Check**: `/health` endpoint

### Nginx Reverse Proxy
- **Container**: `365-nginx`
- **Ports**: 80 (HTTP), 443 (HTTPS)
- **Features**: SSL termination, rate limiting, caching
- **Security**: HSTS, XSS protection, content type validation

### Certbot
- **Container**: `365-certbot`
- **Purpose**: SSL certificate management
- **Method**: Cloudflare DNS challenge
- **Auto-renewal**: Built-in Let's Encrypt renewal

## Configuration Files

### Nginx Configuration
- `nginx/nginx.conf` - Main Nginx configuration
- `nginx/conf.d/owa.shtrum.com.conf` - Domain-specific config
- `nginx/conf.d/proxy_params.conf` - Proxy parameters

### SSL Certificates
- `certbot/conf/` - Let's Encrypt certificates
- `certbot/www/` - Webroot for ACME challenges
- `certbot/cloudflare.ini` - Cloudflare API credentials

## Security Features

### Rate Limiting
- **Login**: 5 requests per minute
- **API**: 10 requests per second
- **Burst**: Additional requests allowed

### SSL Security
- **Protocols**: TLSv1.2, TLSv1.3
- **Ciphers**: Strong encryption only
- **HSTS**: 1 year max-age
- **Session**: 10-minute timeout

### Headers
- `Strict-Transport-Security`
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`

## Monitoring

### Health Checks
```bash
# Check all services
docker-compose ps

# Check email system health
curl https://owa.shtrum.com/health

# View logs
docker-compose logs -f email-system
docker-compose logs -f nginx
```

### Log Files
- **Application**: `./logs/` directory
- **Nginx**: `docker-compose logs nginx`
- **SSL**: `docker-compose logs certbot`

## Maintenance

### SSL Certificate Renewal
Certificates auto-renew, but you can manually renew:
```bash
docker-compose run --rm certbot renew
docker-compose restart nginx
```

### Backup
```bash
# Backup database
docker cp 365-email-system:/app/email_system.db ./backup/

# Backup certificates
cp -r certbot/conf ./backup/
```

### Updates
```bash
# Pull latest images
docker-compose pull

# Rebuild and restart
docker-compose up -d --build
```

## Troubleshooting

### Common Issues

1. **SSL Certificate Issues**
   ```bash
   # Check certificate status
   docker-compose run --rm certbot certificates
   
   # Test DNS resolution
   nslookup owa.shtrum.com
   ```

2. **Service Not Starting**
   ```bash
   # Check logs
   docker-compose logs email-system
   
   # Check configuration
   docker-compose config
   ```

3. **Nginx Issues**
   ```bash
   # Test Nginx configuration
   docker-compose exec nginx nginx -t
   
   # Reload Nginx
   docker-compose exec nginx nginx -s reload
   ```

### Port Conflicts
If ports 80/443 are in use:
```bash
# Check what's using the ports
sudo netstat -tulpn | grep :80
sudo netstat -tulpn | grep :443

# Stop conflicting services
sudo systemctl stop apache2  # or nginx, etc.
```

## Production Considerations

### Security
- Change default `SECRET_KEY`
- Use strong passwords
- Enable firewall rules
- Regular security updates

### Performance
- Monitor resource usage
- Scale services as needed
- Optimize Nginx caching
- Database optimization

### Backup Strategy
- Regular database backups
- Certificate backup
- Configuration backup
- Test restore procedures

## Support

For issues and questions:
1. Check logs: `docker-compose logs`
2. Verify configuration: `docker-compose config`
3. Test connectivity: `curl -I https://owa.shtrum.com`
4. Check DNS: `nslookup owa.shtrum.com`
