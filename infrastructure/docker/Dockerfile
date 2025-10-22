# Use Python 3.11 slim image (mirror to avoid Docker Hub outages)
FROM public.ecr.aws/docker/library/python:3.11-slim

# Set working directory
WORKDIR /app

# Ensure shared modules are importable
# Make both application root and shared src discoverable for module imports
ENV PYTHONPATH=/app:/app/src

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libffi-dev \
        libssl-dev \
        libkrb5-dev \
        krb5-user \
        ca-certificates \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and assets
COPY src ./src
COPY services ./services
COPY scripts ./scripts
COPY resources ./resources
COPY docs ./docs
COPY infrastructure ./infrastructure
COPY logs ./logs
COPY ssl ./ssl


# Copy troubleshooting files if they exist (optional)
# These files were removed in cleanup but docker-compose might reference them

# Create and set permissions for logs and ssl directories
RUN mkdir -p logs && chmod 777 logs
RUN mkdir -p ssl && python scripts/generate_ssl_cert.py

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
# Don't switch to non-root user since we need root for port 25
# USER appuser

# Expose ports
EXPOSE 8001 1026 25

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Default to the combined UI/SMTP gateway
CMD ["python", "services/ui/smtp_gateway.py"]
