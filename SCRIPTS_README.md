# 365 Email System - Scripts Organization

This document explains the organization of management scripts for the 365 Email System Docker deployment.

## 📁 Directory Structure

```
365/
├── powershell_scripts/          # Windows PowerShell scripts
│   ├── setup-ssl.ps1           # SSL certificate setup
│   ├── start-docker.ps1        # Service startup
│   ├── test-docker.ps1         # Comprehensive testing
│   ├── manage-docker.ps1       # Complete management
│   └── README.md               # PowerShell documentation
├── bash_scripts/               # Mac/Linux Bash scripts
│   ├── setup-ssl.sh            # SSL certificate setup
│   ├── start-docker.sh         # Service startup
│   ├── test-docker.sh          # Comprehensive testing
│   ├── manage-docker.sh        # Complete management
│   └── README.md               # Bash documentation
└── SCRIPTS_README.md           # This file
```

## 🎯 Script Categories

### 🔐 SSL Certificate Management
- **Purpose**: Set up SSL certificates using Cloudflare DNS challenge
- **Windows**: `powershell_scripts/setup-ssl.ps1`
- **Mac/Linux**: `bash_scripts/setup-ssl.sh`

### 🚀 Service Startup
- **Purpose**: Start Docker services with health checks
- **Windows**: `powershell_scripts/start-docker.ps1`
- **Mac/Linux**: `bash_scripts/start-docker.sh`

### 🧪 Testing & Validation
- **Purpose**: Comprehensive testing of all services
- **Windows**: `powershell_scripts/test-docker.ps1`
- **Mac/Linux**: `bash_scripts/test-docker.sh`

### 🔧 Management & Operations
- **Purpose**: Complete Docker management tool
- **Windows**: `powershell_scripts/manage-docker.ps1`
- **Mac/Linux**: `bash_scripts/manage-docker.sh`

## 🖥️ Platform-Specific Features

### Windows PowerShell Scripts
- **PowerShell 5.1+** compatibility
- **Windows-specific** error handling
- **Docker Desktop** integration
- **Windows security** features
- **PowerShell Core** support

### Mac/Linux Bash Scripts
- **Bash 4.0+** compatibility
- **Unix-like** error handling
- **Docker CLI** integration
- **System integration** features
- **Cross-platform** compatibility

## 🚀 Quick Start by Platform

### Windows
```powershell
# 1. Set up SSL certificates
.\powershell_scripts\setup-ssl.ps1 -CloudflareEmail "your-email@example.com" -CloudflareApiKey "your-api-key"

# 2. Start services
.\powershell_scripts\start-docker.ps1

# 3. Test setup
.\powershell_scripts\test-docker.ps1

# 4. Manage services
.\powershell_scripts\manage-docker.ps1 -Action status
```

### Mac/Linux
```bash
# 1. Set up SSL certificates
./bash_scripts/setup-ssl.sh -e "your-email@example.com" -k "your-api-key"

# 2. Start services
./bash_scripts/start-docker.sh

# 3. Test setup
./bash_scripts/test-docker.sh

# 4. Manage services
./bash_scripts/manage-docker.sh status
```

## 📋 Common Operations

### SSL Certificate Setup
| Platform | Command |
|----------|---------|
| Windows | `.\powershell_scripts\setup-ssl.ps1 -CloudflareEmail "email" -CloudflareApiKey "key"` |
| Mac/Linux | `./bash_scripts/setup-ssl.sh -e "email" -k "key"` |

### Start Services
| Platform | Command |
|----------|---------|
| Windows | `.\powershell_scripts\start-docker.ps1` |
| Mac/Linux | `./bash_scripts/start-docker.sh` |

### Test Setup
| Platform | Command |
|----------|---------|
| Windows | `.\powershell_scripts\test-docker.ps1` |
| Mac/Linux | `./bash_scripts/test-docker.sh` |

### Manage Services
| Platform | Command |
|----------|---------|
| Windows | `.\powershell_scripts\manage-docker.ps1 -Action <action>` |
| Mac/Linux | `./bash_scripts/manage-docker.sh <action>` |

## 🔧 Prerequisites

### Windows
- **Docker Desktop** installed and running
- **PowerShell 5.1+** or **PowerShell Core 6+**
- **Cloudflare account** with API access
- **Domain** pointing to your server

### Mac/Linux
- **Docker** and **Docker Compose** installed
- **Bash 4.0+** (for advanced features)
- **Cloudflare account** with API access
- **Domain** pointing to your server
- **OpenSSL** (for certificate validation)

## 📊 Health Checks

Both script sets include comprehensive health checks:

- **Container Status**: Verify all containers are running
- **HTTP Endpoints**: Test all web endpoints
- **SSL Certificates**: Validate SSL certificate status
- **Log Analysis**: Check for errors in service logs
- **Port Accessibility**: Verify all required ports are open
- **Database Connectivity**: Test database connections

## 🛠️ Troubleshooting

### Common Issues

1. **Scripts not executable** (Mac/Linux)
   ```bash
   chmod +x bash_scripts/*.sh
   ```

2. **PowerShell execution policy** (Windows)
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

3. **Docker not running**
   ```bash
   # Check Docker status
   docker version
   ```

4. **Services not starting**
   ```bash
   # Check logs
   ./bash_scripts/manage-docker.sh logs
   # or
   .\powershell_scripts\manage-docker.ps1 -Action logs
   ```

## 📈 Performance Tips

- **Use build flags** when starting to ensure latest images
- **Run tests regularly** to verify system health
- **Monitor resources** with status commands
- **Clean up regularly** to free disk space
- **Backup regularly** to prevent data loss

## 🔒 Security Features

- **SSL/TLS encryption** with automatic certificate management
- **Rate limiting** and DDoS protection
- **Security headers** and best practices
- **Container isolation** and resource limits
- **Automatic updates** and vulnerability scanning

## 📞 Support

For issues and questions:
1. **Check logs** with management scripts
2. **Run tests** with testing scripts
3. **Check status** with status commands
4. **Verify configuration** with Docker Compose

## 🎯 Next Steps

1. **Choose your platform** (Windows or Mac/Linux)
2. **Set up environment** (configure `.env` file)
3. **Get SSL certificates** (run setup scripts)
4. **Start services** (run startup scripts)
5. **Test setup** (run testing scripts)
6. **Access system** (visit https://owa.shtrum.com)

## 🔄 Automation

### Windows (Task Scheduler)
- **Daily backups** with `manage-docker.ps1 -Action backup`
- **Weekly updates** with `manage-docker.ps1 -Action update`
- **Monthly cleanup** with `manage-docker.ps1 -Action clean`

### Mac/Linux (Cron Jobs)
- **Daily backups** with `manage-docker.sh backup`
- **Weekly updates** with `manage-docker.sh update`
- **Monthly cleanup** with `manage-docker.sh clean`

The script organization provides a complete management solution for your 365 Email System across all platforms! 🚀
