# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory and set permissions
RUN mkdir -p logs && chmod 777 logs

# Create SSL directory and generate certificates
RUN mkdir -p ssl && python generate_ssl_cert.py

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
# Don't switch to non-root user since we need root for port 25
# USER appuser

# Expose ports
EXPOSE 8001 1026 25

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the application with SMTP on port 25
CMD ["python", "run_smtp25.py"]
