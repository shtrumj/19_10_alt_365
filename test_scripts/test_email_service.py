#!/usr/bin/env python3
"""
Test email service functionality
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, User
from app.email_service import EmailService
from app.models import EmailCreate

def test_email_service():
    """Test email service"""
    try:
        db = SessionLocal()
        
        # Create a test user
        user = db.query(User).filter(User.username == "testuser").first()
        if not user:
            print("Test user not found")
            return
        
        print(f"Found user: {user.username} ({user.email})")
        
        # Test email service
        email_service = EmailService(db)
        
        # Create email data
        email_data = EmailCreate(
            recipient_email="test@gmail.com",
            subject="Test External Email",
            body="This is a test email to external recipient"
        )
        
        print("Sending external email...")
        result = email_service.send_email(email_data, user.id)
        print(f"Email service result: {result}")
        
        db.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_email_service()
