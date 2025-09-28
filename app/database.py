from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

DATABASE_URL = "sqlite:///./email_system.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    sent_emails = relationship("Email", foreign_keys="Email.sender_id", back_populates="sender")
    received_emails = relationship("Email", foreign_keys="Email.recipient_id", back_populates="recipient")

class Email(Base):
    __tablename__ = "emails"
    
    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String, nullable=False)
    body = Column(Text)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for external senders
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for external emails
    is_read = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    is_external = Column(Boolean, default=False)  # Flag for external emails
    external_sender = Column(String, nullable=True)  # Email address for external senders
    external_recipient = Column(String, nullable=True)  # Email address for external recipients
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_emails")
    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="received_emails")

class EmailAttachment(Base):
    __tablename__ = "email_attachments"
    
    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False)
    filename = Column(String, nullable=False)
    content_type = Column(String)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
