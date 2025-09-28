"""
Comprehensive logging configuration for email system debugging
"""
import logging
import os
from datetime import datetime

def setup_logging():
    """Setup comprehensive logging for debugging"""
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Create timestamp for log files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # Console handler
            logging.StreamHandler(),
            # File handler for all logs
            logging.FileHandler(f'logs/email_system_{timestamp}.log'),
            # Separate handler for email parsing
            logging.FileHandler(f'logs/email_parsing_{timestamp}.log')
        ]
    )
    
    # Configure specific loggers
    email_parser_logger = logging.getLogger('app.email_parser')
    email_parser_logger.setLevel(logging.DEBUG)
    
    owa_logger = logging.getLogger('app.routers.owa')
    owa_logger.setLevel(logging.DEBUG)
    
    smtp_logger = logging.getLogger('app.smtp_server')
    smtp_logger.setLevel(logging.DEBUG)
    
    # Create a separate file handler for email parsing
    email_parsing_handler = logging.FileHandler(f'logs/email_parsing_{timestamp}.log')
    email_parsing_handler.setLevel(logging.DEBUG)
    email_parsing_formatter = logging.Formatter('%(asctime)s - EMAIL_PARSING - %(levelname)s - %(message)s')
    email_parsing_handler.setFormatter(email_parsing_formatter)
    email_parser_logger.addHandler(email_parsing_handler)
    
    # Create a separate file handler for OWA
    owa_handler = logging.FileHandler(f'logs/owa_{timestamp}.log')
    owa_handler.setLevel(logging.DEBUG)
    owa_formatter = logging.Formatter('%(asctime)s - OWA - %(levelname)s - %(message)s')
    owa_handler.setFormatter(owa_formatter)
    owa_logger.addHandler(owa_handler)
    
    print(f"🔍 Logging configured:")
    print(f"   📁 Main logs: logs/email_system_{timestamp}.log")
    print(f"   📧 Email parsing: logs/email_parsing_{timestamp}.log")
    print(f"   🌐 OWA: logs/owa_{timestamp}.log")
    
    return logging.getLogger(__name__)

def log_email_parsing_debug(raw_email, parsed_content, method_used):
    """Log detailed email parsing debug information"""
    logger = logging.getLogger('app.email_parser')
    
    logger.info("=" * 80)
    logger.info("🔍 EMAIL PARSING DEBUG SESSION")
    logger.info("=" * 80)
    logger.info(f"📧 Method used: {method_used}")
    logger.info(f"📏 Raw email length: {len(raw_email)} characters")
    logger.info(f"📝 Parsed content length: {len(parsed_content)} characters")
    logger.info(f"✅ Parsed content: '{parsed_content}'")
    logger.info("=" * 80)
    
    # Log raw email structure
    logger.debug("📋 RAW EMAIL STRUCTURE:")
    lines = raw_email.split('\n')
    for i, line in enumerate(lines[:50]):  # First 50 lines
        logger.debug(f"Line {i:3d}: {line}")
    if len(lines) > 50:
        logger.debug(f"... and {len(lines) - 50} more lines")
    
    logger.info("=" * 80)

def log_template_rendering_debug(template_name, context_data):
    """Log template rendering debug information"""
    logger = logging.getLogger('app.routers.owa')
    
    logger.info("=" * 80)
    logger.info(f"🎨 TEMPLATE RENDERING DEBUG: {template_name}")
    logger.info("=" * 80)
    
    if 'email' in context_data:
        email = context_data['email']
        logger.info(f"📧 Email ID: {email.id}")
        logger.info(f"📧 Email Subject: {email.subject}")
        logger.info(f"📧 Email Body Length: {len(email.body)}")
        logger.info(f"📧 Email Body Preview: {email.body[:200]}...")
        
        # Test parsing in template context
        from .email_parser import parse_email_content
        parsed = parse_email_content(email.body)
        logger.info(f"📧 Parsed Content: '{parsed}'")
    
    logger.info("=" * 80)
