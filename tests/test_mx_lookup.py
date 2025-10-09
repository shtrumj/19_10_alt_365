#!/usr/bin/env python3
"""
Test MX lookup functionality
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.mx_lookup import mx_lookup

def test_mx_lookup():
    """Test MX record lookup"""
    try:
        print("Testing MX lookup for gmail.com...")
        mx_records = mx_lookup.get_mx_records("gmail.com")
        print(f"MX records for gmail.com: {mx_records}")
        
        print("\nTesting delivery info for test@gmail.com...")
        delivery_info = mx_lookup.get_delivery_info("test@gmail.com")
        print(f"Delivery info: {delivery_info}")
        
        print("\nTesting MX lookup for trot.co.il...")
        mx_records = mx_lookup.get_mx_records("trot.co.il")
        print(f"MX records for trot.co.il: {mx_records}")
        
        print("\nTesting delivery info for yonatan@trot.co.il...")
        delivery_info = mx_lookup.get_delivery_info("yonatan@trot.co.il")
        print(f"Delivery info: {delivery_info}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_mx_lookup()
