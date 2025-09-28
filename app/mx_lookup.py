"""
MX Record Lookup Service
Handles DNS MX record lookups for external email delivery
"""
import dns.resolver
import dns.exception
import logging
from typing import List, Tuple, Optional
import socket

logger = logging.getLogger(__name__)

class MXLookupService:
    """Service for looking up MX records for email domains"""
    
    def __init__(self):
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = 10
        self.resolver.lifetime = 10
    
    def get_mx_records(self, domain: str) -> List[Tuple[str, int]]:
        """
        Get MX records for a domain
        
        Args:
            domain: Email domain (e.g., 'gmail.com')
            
        Returns:
            List of tuples (hostname, priority) sorted by priority
        """
        try:
            logger.info(f"Looking up MX records for domain: {domain}")
            
            # Clean domain name
            domain = domain.lower().strip()
            if not domain:
                raise ValueError("Empty domain name")
            
            # Query MX records
            mx_records = self.resolver.resolve(domain, 'MX')
            
            # Parse and sort by priority
            mx_list = []
            for record in mx_records:
                hostname = str(record.exchange).rstrip('.')
                priority = record.preference
                mx_list.append((hostname, priority))
            
            # Sort by priority (lower number = higher priority)
            mx_list.sort(key=lambda x: x[1])
            
            logger.info(f"Found {len(mx_list)} MX records for {domain}: {mx_list}")
            return mx_list
            
        except dns.resolver.NXDOMAIN:
            logger.error(f"Domain {domain} does not exist")
            raise ValueError(f"Domain {domain} does not exist")
        except dns.resolver.NoAnswer:
            logger.error(f"No MX records found for domain {domain}")
            raise ValueError(f"No MX records found for domain {domain}")
        except dns.exception.Timeout:
            logger.error(f"DNS timeout for domain {domain}")
            raise ValueError(f"DNS timeout for domain {domain}")
        except Exception as e:
            logger.error(f"DNS lookup error for domain {domain}: {e}")
            raise ValueError(f"DNS lookup error for domain {domain}: {e}")
    
    def get_best_mx_server(self, domain: str) -> Optional[str]:
        """
        Get the best MX server for a domain (highest priority)
        
        Args:
            domain: Email domain
            
        Returns:
            Best MX server hostname or None if not found
        """
        try:
            mx_records = self.get_mx_records(domain)
            if mx_records:
                best_server = mx_records[0][0]  # First record has highest priority
                logger.info(f"Best MX server for {domain}: {best_server}")
                return best_server
            return None
        except Exception as e:
            logger.error(f"Failed to get best MX server for {domain}: {e}")
            return None
    
    def resolve_mx_to_ip(self, mx_hostname: str) -> Optional[str]:
        """
        Resolve MX hostname to IP address
        
        Args:
            mx_hostname: MX server hostname
            
        Returns:
            IP address or None if not found
        """
        try:
            logger.info(f"Resolving MX hostname {mx_hostname} to IP")
            ip_address = socket.gethostbyname(mx_hostname)
            logger.info(f"MX hostname {mx_hostname} resolved to {ip_address}")
            return ip_address
        except socket.gaierror as e:
            logger.error(f"Failed to resolve MX hostname {mx_hostname}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error resolving MX hostname {mx_hostname}: {e}")
            return None
    
    def get_delivery_info(self, email_address: str) -> Optional[dict]:
        """
        Get complete delivery information for an email address
        
        Args:
            email_address: Full email address
            
        Returns:
            Dictionary with delivery information or None if failed
        """
        try:
            # Extract domain from email
            if '@' not in email_address:
                raise ValueError(f"Invalid email address: {email_address}")
            
            domain = email_address.split('@')[1]
            logger.info(f"Getting delivery info for {email_address} (domain: {domain})")
            
            # Get MX records
            mx_records = self.get_mx_records(domain)
            if not mx_records:
                logger.error(f"No MX records found for domain {domain}")
                return None
            
            # Get best MX server
            best_mx = mx_records[0][0]
            
            # Resolve to IP
            ip_address = self.resolve_mx_to_ip(best_mx)
            if not ip_address:
                logger.error(f"Could not resolve MX server {best_mx} to IP")
                return None
            
            delivery_info = {
                'email': email_address,
                'domain': domain,
                'mx_records': mx_records,
                'best_mx_server': best_mx,
                'mx_ip': ip_address,
                'port': 25,  # Standard SMTP port
                'priority': mx_records[0][1]
            }
            
            logger.info(f"Delivery info for {email_address}: {delivery_info}")
            return delivery_info
            
        except Exception as e:
            logger.error(f"Failed to get delivery info for {email_address}: {e}")
            return None

# Global instance
mx_lookup = MXLookupService()
