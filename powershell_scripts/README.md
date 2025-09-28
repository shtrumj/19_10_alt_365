# PowerShell Scripts for 365 Email System

This directory contains PowerShell scripts for managing the 365 Email System on Windows.

## 📁 Scripts Overview

### 🔐 SSL Certificate Management
- **`setup-ssl.ps1`** - Set up SSL certificates using Cloudflare DNS challenge
- **`start-docker.ps1`** - Start the Docker services with health checks
- **`test-docker.ps1`** - Comprehensive testing of all services
- **`manage-docker.ps1`** - Complete Docker management tool

## 🚀 Quick Start

### 1. SSL Certificate Setup
```powershell
# Set up SSL certificates
.\setup-ssl.ps1 -CloudflareEmail "your-email@example.com" -CloudflareApiKey "your-api-key"
```

### 2. Start Services
```powershell
# Start all services
.\start-docker.ps1

# Start with build
.\start-docker.ps1 -Build
```

### 3. Test Setup
```powershell
# Run comprehensive tests
.\test-docker.ps1

# Run quick tests
.\test-docker.ps1 -Quick

# Run with verbose output
.\test-docker.ps1 -Verbose
```

### 4. Manage Services
```powershell
# Start services
.\manage-docker.ps1 -Action start

# Stop services
.\manage-docker.ps1 -Action stop

# View logs
.\manage-docker.ps1 -Action logs -Service email-system -Follow

# Open shell
.\manage-docker.ps1 -Action shell -Service email-system

# Create backup
.\manage-docker.ps1 -Action backup

# Update services
.\manage-docker.ps1 -Action update

# Clean up
.\manage-docker.ps1 -Action clean
```

## 📋 Script Details

### setup-ssl.ps1
Sets up SSL certificates using Cloudflare DNS challenge.

**Parameters:**
- `-CloudflareEmail` (Required): Your Cloudflare email
- `-CloudflareApiKey` (Required): Your Cloudflare API key
- `-Domain` (Optional): Domain name (default: owa.shtrum.com)

**Example:**
```powershell
.\setup-ssl.ps1 -CloudflareEmail "admin@example.com" -CloudflareApiKey "your-api-key"
```

### start-docker.ps1
Starts the Docker services with health checks and status monitoring.

**Parameters:**
- `-Build` (Optional): Build images before starting
- `-Detach` (Optional): Run in background (default: true)

**Example:**
```powershell
.\start-docker.ps1 -Build
```

### test-docker.ps1
Comprehensive testing of all services and endpoints.

**Parameters:**
- `-Verbose` (Optional): Show verbose output
- `-Quick` (Optional): Run quick tests only

**Example:**
```powershell
.\test-docker.ps1 -Verbose
```

### manage-docker.ps1
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
- `-Service` (Optional): Target specific service
- `-Follow` (Optional): Follow logs (for logs action)
- `-Force` (Optional): Force operation (for clean action)

**Examples:**
```powershell
# Start services
.\manage-docker.ps1 -Action start

# View logs for specific service
.\manage-docker.ps1 -Action logs -Service email-system -Follow

# Open shell in email-system container
.\manage-docker.ps1 -Action shell -Service email-system

# Create backup
.\manage-docker.ps1 -Action backup

# Clean up with force
.\manage-docker.ps1 -Action clean -Force
```

## 🔧 Prerequisites

- **Docker Desktop** installed and running
- **PowerShell 5.1+** or **PowerShell Core 6+**
- **Cloudflare account** with API access (for SSL setup)
- **Domain** pointing to your server

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
   ```powershell
   # Check Docker status
   docker version
   ```

2. **Services not starting**
   ```powershell
   # Check logs
   .\manage-docker.ps1 -Action logs
   ```

3. **SSL certificate issues**
   ```powershell
   # Re-run SSL setup
   .\setup-ssl.ps1 -CloudflareEmail "your-email" -CloudflareApiKey "your-key"
   ```

4. **Port conflicts**
   ```powershell
   # Check port usage
   netstat -an | findstr ":80"
   netstat -an | findstr ":443"
   ```

### Log Locations
- **Application logs**: `./logs/` directory
- **Container logs**: `.\manage-docker.ps1 -Action logs`
- **Docker logs**: `docker-compose logs`

## 📈 Performance Tips

- **Use `-Build` flag** when starting to ensure latest images
- **Run tests regularly** with `.\test-docker.ps1`
- **Monitor resources** with `.\manage-docker.ps1 -Action status`
- **Clean up regularly** with `.\manage-docker.ps1 -Action clean`

## 🔒 Security Features

- **SSL/TLS encryption** with automatic certificate management
- **Rate limiting** and DDoS protection
- **Security headers** and best practices
- **Container isolation** and resource limits
- **Automatic updates** and vulnerability scanning

## 📞 Support

For issues and questions:
1. **Check logs**: `.\manage-docker.ps1 -Action logs`
2. **Run tests**: `.\test-docker.ps1 -Verbose`
3. **Check status**: `.\manage-docker.ps1 -Action status`
4. **Verify configuration**: `docker-compose config`

## 🎯 Next Steps

1. **Set up environment**: Configure `.env` file
2. **Get SSL certificates**: Run `.\setup-ssl.ps1`
3. **Start services**: Run `.\start-docker.ps1`
4. **Test setup**: Run `.\test-docker.ps1`
5. **Access system**: Visit https://owa.shtrum.com

The PowerShell scripts provide a complete management solution for your 365 Email System on Windows! 🚀
