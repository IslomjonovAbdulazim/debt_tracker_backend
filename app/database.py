from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.pool import StaticPool
from datetime import datetime
from app.config import settings
import logging

# Setup logging
logger = logging.getLogger(__name__)

# Optimized database setup
engine_kwargs = {
    "connect_args": {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    "echo": False,  # Disable SQL logging for better performance
}

# Add connection pooling for better performance
if "sqlite" in settings.DATABASE_URL:
    # SQLite optimizations
    engine_kwargs.update({
        "poolclass": StaticPool,
        "connect_args": {
            "check_same_thread": False,
            "timeout": 20,
            # SQLite optimizations
            "isolation_level": None  # Autocommit mode for better performance
        }
    })
else:
    # PostgreSQL/MySQL optimizations
    engine_kwargs.update({
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_POOL_OVERFLOW,
        "pool_recycle": settings.DB_POOL_RECYCLE,
        "pool_pre_ping": True,  # Verify connections before use
    })

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Better performance for read operations
)

Base = declarative_base()


# Optimized database models with indexes
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)  # Indexed for fast lookups
    password = Column(String)
    fullname = Column(String)
    is_verified = Column(Boolean, default=False, index=True)  # Indexed for filtering
    created_at = Column(DateTime, default=datetime.utcnow, index=True)  # Indexed for sorting

    # Relationships with lazy loading optimization
    contacts = relationship("Contact", back_populates="user", cascade="all, delete-orphan", lazy="select")


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)  # Indexed for searching
    phone = Column(String, index=True)  # Indexed for searching
    user_id = Column(Integer, ForeignKey("users.id"), index=True)  # Indexed for joins
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="contacts")
    debts = relationship("Debt", back_populates="contact", cascade="all, delete-orphan", lazy="select")


class Debt(Base):
    __tablename__ = "debts"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Float, index=True)  # Indexed for calculations
    description = Column(String)
    is_paid = Column(Boolean, default=False, index=True)  # Indexed for filtering
    is_my_debt = Column(Boolean, index=True)  # Indexed for filtering
    contact_id = Column(Integer, ForeignKey("contacts.id"), index=True)  # Indexed for joins
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    contact = relationship("Contact", back_populates="debts")


class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True)  # Indexed for fast lookups
    code = Column(String, index=True)  # Indexed for verification
    code_type = Column(String, index=True)  # Indexed for filtering
    expires_at = Column(DateTime, index=True)  # Indexed for cleanup
    used = Column(Boolean, default=False, index=True)  # Indexed for filtering
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# Optimized database session management
def get_db():
    """Get database session with proper error handling"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table - optimized"""
    try:
        with engine.connect() as conn:
            if "sqlite" in settings.DATABASE_URL:
                result = conn.execute(text(f"PRAGMA table_info({table_name})"))
                columns = [row[1] for row in result.fetchall()]
                return column_name in columns
            else:
                # For PostgreSQL/MySQL
                result = conn.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = :table_name AND column_name = :column_name"
                ), {"table_name": table_name, "column_name": column_name})
                return result.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking column existence: {e}")
        return False


def optimize_sqlite_settings():
    """Apply SQLite performance optimizations"""
    if "sqlite" in settings.DATABASE_URL:
        try:
            with engine.connect() as conn:
                # Apply SQLite optimizations
                conn.execute(text("PRAGMA journal_mode=WAL"))  # Write-Ahead Logging
                conn.execute(text("PRAGMA synchronous=NORMAL"))  # Faster than FULL
                conn.execute(text("PRAGMA cache_size=10000"))  # 10MB cache
                conn.execute(text("PRAGMA temp_store=MEMORY"))  # Store temp tables in memory
                conn.execute(text("PRAGMA mmap_size=268435456"))  # 256MB memory map
                conn.commit()
                logger.info("SQLite performance optimizations applied")
        except Exception as e:
            logger.warning(f"Could not apply SQLite optimizations: {e}")


def migrate_database():
    """Perform database migrations - optimized"""
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
                optimize_sqlite_settings()
                return

            # Track applied migrations
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

            # Check verification_codes table
            if "sqlite" in settings.DATABASE_URL:
                result = conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name='verification_codes'"))
                vc_table_exists = result.fetchone() is not None
            else:
                result = conn.execute(
                    text("SELECT table_name FROM information_schema.tables WHERE table_name = 'verification_codes'"))
                vc_table_exists = result.fetchone() is not None

            if vc_table_exists and not check_column_exists("verification_codes", "used"):
                logger.info("Adding used column to verification_codes table...")
                if "sqlite" in settings.DATABASE_URL:
                    conn.execute(text("ALTER TABLE verification_codes ADD COLUMN used BOOLEAN DEFAULT 0"))
                else:
                    conn.execute(text("ALTER TABLE verification_codes ADD COLUMN used BOOLEAN DEFAULT FALSE"))
                conn.commit()
                migrations_applied.append("Added used column to verification_codes table")

            # Create indexes for better performance (if they don't exist)
            try:
                if "sqlite" in settings.DATABASE_URL:
                    # Create composite indexes for common queries
                    conn.execute(text(
                        "CREATE INDEX IF NOT EXISTS idx_verification_codes_email_type ON verification_codes(email, code_type)"))
                    conn.execute(text(
                        "CREATE INDEX IF NOT EXISTS idx_verification_codes_expires_used ON verification_codes(expires_at, used)"))
                    conn.execute(
                        text("CREATE INDEX IF NOT EXISTS idx_debts_contact_paid ON debts(contact_id, is_paid)"))
                    conn.execute(
                        text("CREATE INDEX IF NOT EXISTS idx_debts_contact_type ON debts(contact_id, is_my_debt)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_contacts_user_phone ON contacts(user_id, phone)"))
                    conn.commit()
                    migrations_applied.append("Created performance indexes")
            except Exception as e:
                logger.warning(f"Could not create indexes: {e}")

            if migrations_applied:
                logger.info(f"Applied migrations: {', '.join(migrations_applied)}")
            else:
                logger.info("No migrations needed, database schema is up to date")

            # Apply SQLite optimizations
            optimize_sqlite_settings()

    except Exception as e:
        logger.error(f"Error during migration: {e}")
        raise


def create_tables():
    """Create tables and apply migrations - optimized"""
    try:
        migrate_database()
        # Ensure all tables are created (handles new tables)
        Base.metadata.create_all(bind=engine)

        # Additional performance optimizations
        optimize_sqlite_settings()

        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Error creating/migrating database: {e}")
        raise


def cleanup_expired_codes():
    """Clean up expired verification codes from database"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "DELETE FROM verification_codes WHERE expires_at < :now OR used = 1"
            ), {"now": datetime.utcnow()})

            deleted_count = result.rowcount
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired/used verification codes")

            conn.commit()
            return deleted_count
    except Exception as e:
        logger.error(f"Error cleaning up verification codes: {e}")
        return 0


def get_database_stats():
    """Get database statistics for monitoring"""
    try:
        with engine.connect() as conn:
            stats = {}

            # Count records in each table
            for table in ['users', 'contacts', 'debts', 'verification_codes']:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                stats[f"{table}_count"] = result.scalar()

            # Additional stats
            if "sqlite" in settings.DATABASE_URL:
                # SQLite specific stats
                result = conn.execute(text("PRAGMA page_count"))
                page_count = result.scalar()

                result = conn.execute(text("PRAGMA page_size"))
                page_size = result.scalar()

                stats["database_size_mb"] = round((page_count * page_size) / (1024 * 1024), 2)

                # Check journal mode
                result = conn.execute(text("PRAGMA journal_mode"))
                stats["journal_mode"] = result.scalar()

            return stats
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {"error": str(e)}


# Performance monitoring
def check_database_performance():
    """Check database performance"""
    try:
        import time
        start_time = time.time()

        with engine.connect() as conn:
            # Simple performance test
            conn.execute(text("SELECT 1"))

        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)  # milliseconds

        return {
            "status": "healthy",
            "response_time_ms": response_time,
            "connection_pool_size": engine.pool.size() if hasattr(engine.pool, 'size') else "N/A",
            "checked_out_connections": engine.pool.checkedout() if hasattr(engine.pool, 'checkedout') else "N/A"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }