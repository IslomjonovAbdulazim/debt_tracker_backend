# app/database.py
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from datetime import datetime

# Get database URL from environment variable or use SQLite as fallback
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./debt_tracker.db")

# Create engine - works for both PostgreSQL and SQLite
if DATABASE_URL.startswith("postgresql"):
    engine = create_engine(DATABASE_URL)
else:
    # SQLite fallback for local development
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create session for database operations
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()


# Function to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Function to create all tables
def create_tables():
    Base.metadata.create_all(bind=engine)


# Database Models (Tables) - Same as before

# Users table
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)  # Will be hashed
    fullname = Column(String)
    is_email_verified = Column(Boolean, default=False)  # Email verification status
    created_at = Column(DateTime, default=datetime.now)

    # Relationship: one user has many contacts
    contacts = relationship("Contact", back_populates="owner")


# Contacts table
class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    fullname = Column(String)
    phone_number = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))  # Which user owns this contact
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    owner = relationship("User", back_populates="contacts")
    debts = relationship("Debt", back_populates="contact")


# Debts table
class Debt(Base):
    __tablename__ = "debts"

    id = Column(Integer, primary_key=True, index=True)
    debt_amount = Column(Float)
    description = Column(String)
    due_date = Column(DateTime)
    is_paid = Column(Boolean, default=False)
    is_my_debt = Column(Boolean)  # True = I owe them, False = they owe me
    contact_id = Column(Integer, ForeignKey("contacts.id"))
    created_at = Column(DateTime, default=datetime.now)

    # Relationship
    contact = relationship("Contact", back_populates="debts")


# Verification codes table
class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True)
    code = Column(String)
    code_type = Column(String)  # "email_verification" or "password_reset"
    created_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime)
    is_used = Column(Boolean, default=False)