#!/usr/bin/env python3
"""
SMTP Communication Logger
Separates internal and external SMTP communications
"""
import logging
import os
from datetime import datetime
from typing import Optional
import json

class SMTPLogger:
    def __init__(self):
        self.logs_dir = "logs"
        self.ensure_logs_directory()
        
        # Internal SMTP logger (our server receiving emails)
        self.internal_logger = self._setup_logger(
            "internal_smtp",
            os.path.join(self.logs_dir, "internal_smtp.log"),
            "Internal SMTP Server"
        )
        
        # External SMTP logger (our server sending emails)
        self.external_logger = self._setup_logger(
            "external_smtp", 
            os.path.join(self.logs_dir, "external_smtp.log"),
            "External SMTP Client"
        )
        
        # Connection logger (all SMTP connections)
        self.connection_logger = self._setup_logger(
            "smtp_connections",
            os.path.join(self.logs_dir, "smtp_connections.log"),
            "SMTP Connections"
        )
        
        # Email processing logger
        self.processing_logger = self._setup_logger(
            "email_processing",
            os.path.join(self.logs_dir, "email_processing.log"),
            "Email Processing"
        )

    def ensure_logs_directory(self):
        """Ensure logs directory exists"""
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)

    def _setup_logger(self, name: str, log_file: str, description: str) -> logging.Logger:
        """Setup a logger with file and console output"""
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Try to create file handler, fall back to console only if permission denied
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            
            # Formatter
            formatter = logging.Formatter(
                f'%(asctime)s - {description} - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except PermissionError:
            # If we can't write to log file, just use console
            pass
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            f'%(asctime)s - {description} - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger

    def log_internal_connection(self, peer_address: str, peer_port: int):
        """Log incoming connection to our SMTP server"""
        self.internal_logger.info(f"📥 INCOMING CONNECTION from {peer_address}:{peer_port}")
        self.connection_logger.info(f"Connection from {peer_address}:{peer_port}")

    def log_internal_command(self, command: str, response: str = ""):
        """Log SMTP commands received by our server"""
        self.internal_logger.debug(f"📨 COMMAND: {command}")
        if response:
            self.internal_logger.debug(f"📤 RESPONSE: {response}")

    def log_internal_email_received(self, sender: str, recipient: str, subject: str, size: int):
        """Log email received by our server"""
        self.internal_logger.info(f"📧 EMAIL RECEIVED - From: {sender}, To: {recipient}, Subject: {subject}, Size: {size} bytes")
        self.processing_logger.info(f"Processing email: {sender} -> {recipient}")

    def log_external_connection(self, server: str, port: int):
        """Log outgoing connection to external SMTP server"""
        self.external_logger.info(f"📤 OUTGOING CONNECTION to {server}:{port}")
        self.connection_logger.info(f"Connecting to external server {server}:{port}")

    def log_external_command(self, command: str, response: str = ""):
        """Log SMTP commands sent to external servers"""
        self.external_logger.debug(f"📤 COMMAND: {command}")
        if response:
            self.external_logger.debug(f"📥 RESPONSE: {response}")

    def log_external_email_sent(self, sender: str, recipient: str, subject: str, server: str):
        """Log email sent to external server"""
        self.external_logger.info(f"📧 EMAIL SENT - From: {sender}, To: {recipient}, Subject: {subject}, Via: {server}")

    def log_email_processing(self, action: str, details: dict):
        """Log email processing actions"""
        self.processing_logger.info(f"🔄 {action}: {json.dumps(details, indent=2)}")

    def log_error(self, error_type: str, error_message: str, context: dict = None):
        """Log errors with context"""
        error_details = {
            "error_type": error_type,
            "error_message": error_message,
            "context": context or {},
            "timestamp": datetime.now().isoformat()
        }
        
        self.internal_logger.error(f"❌ ERROR: {error_type} - {error_message}")
        self.processing_logger.error(f"❌ {error_type}: {error_message}")
        
        # Save detailed error log
        error_log_file = os.path.join(self.logs_dir, "smtp_errors.log")
        try:
            with open(error_log_file, "a") as f:
                f.write(json.dumps(error_details, indent=2) + "\n")
        except PermissionError:
            # If we can't write to log file, just use console
            pass

    def log_smtp_server_status(self, status: str, details: dict = None):
        """Log SMTP server status changes"""
        self.internal_logger.info(f"🔄 SERVER STATUS: {status}")
        if details:
            self.internal_logger.debug(f"Status details: {json.dumps(details, indent=2)}")

# Global logger instance
smtp_logger = SMTPLogger()
