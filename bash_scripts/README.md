# Bash Scripts for 365 Email System

This directory contains Bash scripts for managing the 365 Email System on Mac/Linux.

## 📁 Scripts Overview

### 🔐 SSL Certificate Management
- **`setup-ssl.sh`** - Set up SSL certificates using Cloudflare DNS challenge
- **`start-docker.sh`** - Start the Docker services with health checks
- **`test-docker.sh`** - Comprehensive testing of all services
- **`manage-docker.sh`** - Complete Docker management tool

## 🚀 Quick Start

### 1. SSL Certificate Setup
```bash
# Set up SSL certificates
./setup-ssl.sh -e "your-email@example.com" -k "your-api-key"

# With custom domain
./setup-ssl.sh -e "your-email@example.com" -k "your-api-key" -d "custom.domain.com"
```

### 2. Start Services
```bash
# Start all services
./start-docker.sh

# Start with build
./start-docker.sh --build

# Start in foreground
./start-docker.sh --foreground
```

### 3. Test Setup
```bash
# Run comprehensive tests
./test-docker.sh

# Run quick tests
./test-docker.sh --quick

# Run with verbose output
./test-docker.sh --verbose
```

### 4. Manage Services
```bash
# Start services
./manage-docker.sh start

# Stop services
./manage-docker.sh stop

# View logs
./manage-docker.sh logs -s email-system -f

# Open shell
./manage-docker.sh shell -s email-system

# Create backup
./manage-docker.sh backup

# Update services
./manage-docker.sh update

# Clean up
./manage-docker.sh clean --force
```

## 📋 Script Details

### setup-ssl.sh
Sets up SSL certificates using Cloudflare DNS challenge.

**Parameters:**
- `-e, --email` (Required): Your Cloudflare email
- `-k, --api-key` (Required): Your Cloudflare API key
- `-d, --domain` (Optional): Domain name (default: owa.shtrum.com)
- `-h, --help`: Show help message

**Example:**
```bash
./setup-ssl.sh -e "admin@example.com" -k "your-api-key"
```

### start-docker.sh
Starts the Docker services with health checks and status monitoring.

**Parameters:**
- `-b, --build` (Optional): Build images before starting
- `-f, --foreground` (Optional): Run in foreground (don't detach)
- `-h, --help`: Show help message

**Example:**
```bash
./start-docker.sh --build
```

### test-docker.sh
Comprehensive testing of all services and endpoints.

**Parameters:**
- `-v, --verbose` (Optional): Show verbose output
- `-q, --quick` (Optional): Run quick tests only
- `-h, --help`: Show help message

**Example:**
```bash
./test-docker.sh --verbose
```

### manage-docker.sh
Complete Docker management tool with multiple actions.

**Actions:**
- `start` - Start all services
- `stop` - Stop all services
- `restart` - Restart all services
- `status` - Show service status
- `logs` - Show service logs
- `shell` - Open shell in container
- `backup` - Create backup
- `update` - Update services
- `clean` - Clean up Docker resources

**Parameters:**
- `-s, --service <name>` (Optional): Target specific service
- `-f, --follow` (Optional): Follow logs (for logs action)
- `--force` (Optional): Force operation (for clean action)
- `-h, --help`: Show help message

**Examples:**
```bash
# Start services
./manage-docker.sh start

# View logs for specific service
./manage-docker.sh logs -s email-system -f

# Open shell in email-system container
./manage-docker.sh shell -s email-system

# Create backup
./manage-docker.sh backup

# Clean up with force
./manage-docker.sh clean --force
```

## 🔧 Prerequisites

- **Docker** and **Docker Compose** installed
- **Bash 4.0+** (for advanced features)
- **Cloudflare account** with API access (for SSL setup)
- **Domain** pointing to your server
- **OpenSSL** (for certificate validation)

## 📊 Health Checks

All scripts include comprehensive health checks:

- **Container Status**: Verify all containers are running
- **HTTP Endpoints**: Test all web endpoints
- **SSL Certificates**: Validate SSL certificate status
- **Log Analysis**: Check for errors in service logs
- **Port Accessibility**: Verify all required ports are open
- **Database Connectivity**: Test database connections

## 🛠️ Troubleshooting

### Common Issues

1. **Docker not running**
   ```bash
   # Check Docker status
   docker version
   ```

2. **Services not starting**
   ```bash
   # Check logs
   ./manage-docker.sh logs
   ```

3. **SSL certificate issues**
   ```bash
   # Re-run SSL setup
   ./setup-ssl.sh -e "your-email" -k "your-key"
   ```

4. **Port conflicts**
   ```bash
   # Check port usage
   netstat -tulpn | grep :80
   netstat -tulpn | grep :443
   ```

5. **Permission issues**
   ```bash
   # Make scripts executable
   chmod +x *.sh
   ```

### Log Locations
- **Application logs**: `./logs/` directory
- **Container logs**: `./manage-docker.sh logs`
- **Docker logs**: `docker-compose logs`

## 📈 Performance Tips

- **Use `--build` flag** when starting to ensure latest images
- **Run tests regularly** with `./test-docker.sh`
- **Monitor resources** with `./manage-docker.sh status`
- **Clean up regularly** with `./manage-docker.sh clean`

## 🔒 Security Features

- **SSL/TLS encryption** with automatic certificate management
- **Rate limiting** and DDoS protection
- **Security headers** and best practices
- **Container isolation** and resource limits
- **Automatic updates** and vulnerability scanning

## 🐧 Linux-Specific Features

- **Systemd integration** for service management
- **Log rotation** and management
- **Resource monitoring** with system tools
- **Backup automation** with cron jobs
- **Security hardening** with SELinux/AppArmor

## 🍎 macOS-Specific Features

- **Docker Desktop integration** for seamless management
- **Homebrew compatibility** for easy installation
- **macOS security** with Gatekeeper and notarization
- **Resource optimization** for Apple Silicon
- **Integration** with macOS networking

## 📞 Support

For issues and questions:
1. **Check logs**: `./manage-docker.sh logs`
2. **Run tests**: `./test-docker.sh --verbose`
3. **Check status**: `./manage-docker.sh status`
4. **Verify configuration**: `docker-compose config`

## 🎯 Next Steps

1. **Set up environment**: Configure `.env` file
2. **Get SSL certificates**: Run `./setup-ssl.sh`
3. **Start services**: Run `./start-docker.sh`
4. **Test setup**: Run `./test-docker.sh`
5. **Access system**: Visit https://owa.shtrum.com

## 🔄 Automation

### Cron Jobs (Linux)
```bash
# Add to crontab for automatic backups
0 2 * * * /path/to/365/bash_scripts/manage-docker.sh backup

# Add to crontab for automatic updates
0 3 * * 0 /path/to/365/bash_scripts/manage-docker.sh update
```

### LaunchAgent (macOS)
```xml
<!-- Create ~/Library/LaunchAgents/com.365email.backup.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.365email.backup</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/365/bash_scripts/manage-docker.sh</string>
        <string>backup</string>
    </array>
    <key>StartInterval</key>
    <integer>86400</integer>
</dict>
</plist>
```

The Bash scripts provide a complete management solution for your 365 Email System on Mac/Linux! 🚀
