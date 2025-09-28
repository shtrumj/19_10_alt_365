#!/usr/bin/env python3
"""
Script to reset password for existing user
"""
import sys
import os
sys.path.append('/Users/jonathanshtrum/Downloads/365')

from app.database import SessionLocal, User
from app.auth import get_password_hash

def reset_user_password():
    """Reset password for yonatan user"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == 'yonatan').first()
        if user:
            # Set a simple password
            new_password = "password123"
            user.hashed_password = get_password_hash(new_password)
            db.commit()
            print(f"Password reset for user {user.username}")
            print(f"New password: {new_password}")
            return True
        else:
            print("User not found")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    reset_user_password()
