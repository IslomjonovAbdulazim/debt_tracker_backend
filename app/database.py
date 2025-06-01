from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from app.config import settings
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Database models
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    fullname = Column(String)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    contacts = relationship("Contact", back_populates="user", cascade="all, delete-orphan")


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    phone = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="contacts")
    debts = relationship("Debt", back_populates="contact", cascade="all, delete-orphan")


class Debt(Base):
    __tablename__ = "debts"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Float)
    description = Column(String)
    is_paid = Column(Boolean, default=False)
    is_my_debt = Column(Boolean)  # True = I owe them, False = they owe me
    contact_id = Column(Integer, ForeignKey("contacts.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    contact = relationship("Contact", back_populates="debts")


class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True)
    code = Column(String)
    code_type = Column(String)  # "email" or "password_reset"
    expires_at = Column(DateTime)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# Database functions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    try:
        with engine.connect() as conn:
            if "sqlite" in settings.DATABASE_URL:
                result = conn.execute(text(f"PRAGMA table_info({table_name})"))
                columns = [row[1] for row in result.fetchall()]
                return column_name in columns
            else:
                # For PostgreSQL/MySQL
                result = conn.execute(text(
                    f"SELECT column_name FROM information_schema.columns "
                    f"WHERE table_name = '{table_name}' AND column_name = '{column_name}'"
                ))
                return result.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking column existence: {e}")
        return False


def migrate_database():
    """Perform database migrations"""
    logger.info("Checking for database migrations...")

    try:
        with engine.connect() as conn:
            # Check if users table exists
            if "sqlite" in settings.DATABASE_URL:
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'"))
                table_exists = result.fetchone() is not None
            else:
                result = conn.execute(
                    text("SELECT table_name FROM information_schema.tables WHERE table_name = 'users'"))
                table_exists = result.fetchone() is not None

            if not table_exists:
                logger.info("Users table doesn't exist, creating all tables...")
                Base.metadata.create_all(bind=engine)
                return

            # Check and add missing columns
            migrations_applied = []

            # Add is_verified column to users table if it doesn't exist
            if not check_column_exists("users", "is_verified"):
                logger.info("Adding is_verified column to users table...")
                if "sqlite" in settings.DATABASE_URL:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 0"))
                else:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT FALSE"))
                conn.commit()
                migrations_applied.append("Added is_verified column to users table")

            # Check if verification_codes table exists and add missing columns
            if "sqlite" in settings.DATABASE_URL:
                result = conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name='verification_codes'"))
                vc_table_exists = result.fetchone() is not None
            else:
                result = conn.execute(
                    text("SELECT table_name FROM information_schema.tables WHERE table_name = 'verification_codes'"))
                vc_table_exists = result.fetchone() is not None

            if vc_table_exists:
                # Add used column to verification_codes table if it doesn't exist
                if not check_column_exists("verification_codes", "used"):
                    logger.info("Adding used column to verification_codes table...")
                    if "sqlite" in settings.DATABASE_URL:
                        conn.execute(text("ALTER TABLE verification_codes ADD COLUMN used BOOLEAN DEFAULT 0"))
                    else:
                        conn.execute(text("ALTER TABLE verification_codes ADD COLUMN used BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    migrations_applied.append("Added used column to verification_codes table")

            # You can add more migration checks here for future schema changes
            # Example:
            # if not check_column_exists("users", "new_column"):
            #     conn.execute(text("ALTER TABLE users ADD COLUMN new_column VARCHAR(255)"))
            #     migrations_applied.append("Added new_column to users table")

            if migrations_applied:
                logger.info(f"Applied migrations: {', '.join(migrations_applied)}")
            else:
                logger.info("No migrations needed, database schema is up to date")

    except Exception as e:
        logger.error(f"Error during migration: {e}")
        raise


def create_tables():
    """Create tables and apply migrations"""
    try:
        migrate_database()
        # Ensure all tables are created (handles new tables)
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Error creating/migrating database: {e}")
        raise