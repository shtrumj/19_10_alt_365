"""
Configuration module for the 365 Email System
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    """Application settings loaded from environment variables"""
    
    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production-make-it-long-and-random")
    
    # Database
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/email_system",
    )
    
    # Domain and Hostname
    DOMAIN = os.getenv("DOMAIN", "owa.shtrum.com")
    HOSTNAME = os.getenv("HOSTNAME", "owa.shtrum.com")
    
    # Email System
    SMTP_HOST = os.getenv("SMTP_HOST", "0.0.0.0")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "1026"))
    WEB_PORT = int(os.getenv("WEB_PORT", "8001"))
    
    # Cloudflare API (for SSL certificates)
    CLOUDFLARE_EMAIL = os.getenv("CLOUDFLARE_EMAIL", "shtrumj@gmail.com")
    CLOUDFLARE_API_KEY = os.getenv("CLOUDFLARE_API_KEY", "")
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Global settings instance
settings = Settings()
