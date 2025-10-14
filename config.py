import os

from dotenv import load_dotenv

load_dotenv()

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./email_system.db")

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# SMTP Server
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))

# Application
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# ActiveSync logging flags
AS_LOG_SPLIT = os.getenv("AS_LOG_SPLIT", "1") not in ("0", "false", "False")
AS_REDACT = os.getenv("AS_REDACT", "0") in ("1", "true", "True")
AS_MAX_WINDOW_SIZE = int(os.getenv("AS_MAX_WINDOW_SIZE", "25"))
