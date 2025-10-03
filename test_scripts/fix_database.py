#!/usr/bin/env python3
"""
Fix database schema by recreating with new columns
"""
import os
import shutil
from datetime import datetime

def backup_and_recreate_database():
    """Backup existing database and recreate with new schema"""
    db_path = "email_system.db"
    
    if os.path.exists(db_path):
        # Create backup
        backup_path = f"email_system_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(db_path, backup_path)
        print(f"✅ Database backed up to: {backup_path}")
        
        # Remove old database
        os.remove(db_path)
        print("✅ Old database removed")
    
    # Import and create new database
    try:
        from app.database import create_tables, engine
        from app.email_queue import Base as QueueBase
        
        print("Creating new database with updated schema...")
        create_tables()
        QueueBase.metadata.create_all(bind=engine)
        print("✅ New database created successfully!")
        
        # Create a test user
        from app.database import SessionLocal, User
        from app.auth import get_password_hash
        
        db = SessionLocal()
        try:
            # Check if user exists
            existing_user = db.query(User).filter(User.email == "yonatan@shtrum.com").first()
            if not existing_user:
                # Create test user
                test_user = User(
                    username="yonatan",
                    email="yonatan@shtrum.com",
                    full_name="Yehonathan Shtrum",
                    hashed_password=get_password_hash("Gib$0n579!")
                )
                db.add(test_user)
                db.commit()
                print("✅ Test user created: yonatan@shtrum.com")
            else:
                print("✅ Test user already exists: yonatan@shtrum.com")
        except Exception as e:
            print(f"❌ Error creating test user: {e}")
            db.rollback()
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🔧 Fixing database schema...")
    if backup_and_recreate_database():
        print("✅ Database fixed successfully!")
    else:
        print("❌ Database fix failed!")
