"""
SMTP Client for External Email Delivery
Handles sending emails to external SMTP servers
"""
import smtplib
import ssl
import logging
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formatdate, make_msgid
from typing import Dict, List, Optional, Tuple
import socket
import time
from .smtp_logger import smtp_logger

logger = logging.getLogger(__name__)

class SMTPDeliveryResult:
    """Result of SMTP delivery attempt"""
    
    def __init__(self, success: bool, error_message: str = None, response_code: int = None):
        self.success = success
        self.error_message = error_message
        self.response_code = response_code
        self.timestamp = time.time()

class SMTPClient:
    """SMTP client for external email delivery"""
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.connection_pool = {}  # Connection pooling for efficiency
    
    def create_email_message(self, 
                           sender: str, 
                           recipient: str, 
                           subject: str, 
                           body: str,
                           headers: Dict = None) -> MIMEMultipart:
        """
        Create email message object
        
        Args:
            sender: Sender email address
            recipient: Recipient email address
            subject: Email subject
            body: Email body
            headers: Additional headers
            
        Returns:
            MIMEMultipart message object
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = sender
            msg['To'] = recipient
            msg['Subject'] = subject

            # RFC compliance headers
            provided_headers = headers or {}
            message_id = provided_headers.get('Message-ID') or make_msgid(domain=sender.split('@')[-1])
            msg['Message-ID'] = message_id
            msg['Date'] = formatdate(localtime=True)
            msg['MIME-Version'] = '1.0'

            # Add custom headers
            if provided_headers:
                for key, value in provided_headers.items():
                    if key.lower() not in ['from', 'to', 'subject', 'message-id', 'date', 'mime-version']:
                        msg[key] = value
            
            # Add body
            if body:
                # Try to detect if body is HTML
                if '<html>' in body.lower() or '<body>' in body.lower():
                    msg.attach(MIMEText(body, 'html'))
                else:
                    msg.attach(MIMEText(body, 'plain'))
            
            logger.debug(f"Created email message from {sender} to {recipient}")
            return msg
            
        except Exception as e:
            logger.error(f"Error creating email message: {e}")
            raise
    
    def connect_to_server(self, hostname: str, port: int = 25, use_tls: bool = True) -> Optional[smtplib.SMTP]:
        """
        Connect to SMTP server
        
        Args:
            hostname: SMTP server hostname
            port: SMTP server port
            use_tls: Whether to use TLS
            
        Returns:
            SMTP connection object or None if failed
        """
        try:
            logger.info(f"Connecting to SMTP server {hostname}:{port}")
            
            # Create connection
            server = smtplib.SMTP(hostname, port, timeout=self.timeout)
            server.set_debuglevel(0)  # Set to 1 for debug output
            
            # Start TLS if requested
            if use_tls:
                try:
                    server.starttls()
                    logger.info(f"Started TLS with {hostname}")
                except Exception as e:
                    logger.warning(f"TLS failed with {hostname}, continuing without: {e}")
            
            logger.info(f"Successfully connected to {hostname}:{port}")
            return server
            
        except socket.timeout:
            logger.error(f"Connection timeout to {hostname}:{port}")
            return None
        except socket.gaierror as e:
            logger.error(f"DNS resolution failed for {hostname}: {e}")
            return None
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error connecting to {hostname}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error connecting to {hostname}: {e}")
            return None
    
    def send_email(self, 
                   server: smtplib.SMTP,
                   sender: str, 
                   recipient: str, 
                   message: MIMEMultipart) -> SMTPDeliveryResult:
        """
        Send email through SMTP server
        
        Args:
            server: SMTP server connection
            sender: Sender email address
            recipient: Recipient email address
            message: Email message object
            
        Returns:
            SMTPDeliveryResult object
        """
        try:
            logger.info(f"Sending email from {sender} to {recipient}")
            
            # Send email
            text = message.as_string()
            server.sendmail(sender, recipient, text)
            
            logger.info(f"Successfully sent email from {sender} to {recipient}")
            return SMTPDeliveryResult(success=True)
            
        except smtplib.SMTPRecipientsRefused as e:
            error_msg = f"Recipient refused: {e}"
            logger.error(error_msg)
            return SMTPDeliveryResult(success=False, error_message=error_msg)
        except smtplib.SMTPDataError as e:
            error_msg = f"Data error: {e}"
            logger.error(error_msg)
            return SMTPDeliveryResult(success=False, error_message=error_msg)
        except smtplib.SMTPException as e:
            error_msg = f"SMTP error: {e}"
            logger.error(error_msg)
            return SMTPDeliveryResult(success=False, error_message=error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            logger.error(error_msg)
            return SMTPDeliveryResult(success=False, error_message=error_msg)
    
    def deliver_email(self, 
                     sender: str, 
                     recipient: str, 
                     subject: str, 
                     body: str,
                     headers: Dict = None,
                     mx_server: str = None,
                     mx_port: int = 25) -> SMTPDeliveryResult:
        """
        Deliver email to external server
        
        Args:
            sender: Sender email address
            recipient: Recipient email address
            subject: Email subject
            body: Email body
            headers: Additional headers
            mx_server: MX server hostname
            mx_port: MX server port
            
        Returns:
            SMTPDeliveryResult object
        """
        if not mx_server:
            return SMTPDeliveryResult(
                success=False, 
                error_message="No MX server provided"
            )
        
        server = None
        try:
            # Create email message
            message = self.create_email_message(sender, recipient, subject, body, headers)
            
            # Connect to server
            server = self.connect_to_server(mx_server, mx_port)
            if not server:
                return SMTPDeliveryResult(
                    success=False,
                    error_message=f"Failed to connect to {mx_server}:{mx_port}"
                )
            
            # Send email
            result = self.send_email(server, sender, recipient, message)
            return result
            
        except Exception as e:
            error_msg = f"Delivery error: {e}"
            logger.error(error_msg)
            return SMTPDeliveryResult(success=False, error_message=error_msg)
        
        finally:
            # Close connection
            if server:
                try:
                    server.quit()
                    logger.debug(f"Closed connection to {mx_server}")
                except:
                    pass
    
    def test_connection(self, hostname: str, port: int = 25) -> bool:
        """
        Test connection to SMTP server
        
        Args:
            hostname: SMTP server hostname
            port: SMTP server port
            
        Returns:
            True if connection successful
        """
        try:
            server = self.connect_to_server(hostname, port)
            if server:
                server.quit()
                return True
            return False
        except Exception as e:
            logger.error(f"Connection test failed for {hostname}:{port}: {e}")
            return False

# Global SMTP client instance
smtp_client = SMTPClient()
