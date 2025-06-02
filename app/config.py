import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./debt_tracker.db")

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"

    # Email Configuration
    MAIL_USERNAME: str = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD: str = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM: str = os.getenv("MAIL_FROM", "")

    # Email Features - Optimized for performance
    SKIP_EMAIL_SEND: bool = os.getenv("SKIP_EMAIL_SEND", "False").lower() == "true"
    EMAIL_RATE_LIMIT: int = int(os.getenv("EMAIL_RATE_LIMIT", "5"))  # Increased for better UX
    EMAIL_RATE_WINDOW: int = int(os.getenv("EMAIL_RATE_WINDOW", "300"))  # seconds (5 min)

    # Email Timeouts - Reduced for faster response
    EMAIL_TIMEOUT: int = int(os.getenv("EMAIL_TIMEOUT", "10"))  # seconds
    EMAIL_MAX_RETRIES: int = int(os.getenv("EMAIL_MAX_RETRIES", "2"))  # reduced retries
    EMAIL_RETRY_DELAY: int = int(os.getenv("EMAIL_RETRY_DELAY", "1"))  # seconds

    # OTP Settings
    EMAIL_VERIFICATION_EXPIRY: int = int(os.getenv("EMAIL_VERIFICATION_EXPIRY", "10"))  # minutes
    PASSWORD_RESET_EXPIRY: int = int(os.getenv("PASSWORD_RESET_EXPIRY", "15"))  # minutes

    # Performance Settings
    ENABLE_BACKGROUND_EMAILS: bool = os.getenv("ENABLE_BACKGROUND_EMAILS", "True").lower() == "true"
    ENABLE_TEMP_CODE_FALLBACK: bool = os.getenv("ENABLE_TEMP_CODE_FALLBACK", "True").lower() == "true"

    # Database Performance
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_POOL_OVERFLOW: int = int(os.getenv("DB_POOL_OVERFLOW", "10"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))  # 1 hour

    # App
    APP_NAME: str = os.getenv("APP_NAME", "Debt Tracker API")
    APP_VERSION: str = os.getenv("APP_VERSION", "2.1.0")

    # Server Configuration
    SERVER_ENVIRONMENT: str = os.getenv("SERVER_ENVIRONMENT", "development")

    # Network Settings
    NETWORK_CHECK_TIMEOUT: int = int(os.getenv("NETWORK_CHECK_TIMEOUT", "3"))  # seconds

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO" if not os.getenv("DEBUG", "True").lower() == "true" else "DEBUG")

    # External Email Services (Optional - for production)
    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    MAILGUN_API_KEY: str = os.getenv("MAILGUN_API_KEY", "")
    MAILGUN_DOMAIN: str = os.getenv("MAILGUN_DOMAIN", "")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")

    # Emergency/Fallback Settings
    ALLOW_MANUAL_VERIFICATION: bool = os.getenv("ALLOW_MANUAL_VERIFICATION", "True").lower() == "true"
    EMERGENCY_BYPASS_EMAIL: bool = os.getenv("EMERGENCY_BYPASS_EMAIL", "False").lower() == "true"

    # Code Exposure Settings
    EXPOSE_CODES_ON_EMAIL_FAILURE: bool = os.getenv("EXPOSE_CODES_ON_EMAIL_FAILURE", "True").lower() == "true"
    HIDE_CODES_IN_PRODUCTION: bool = os.getenv("HIDE_CODES_IN_PRODUCTION", "False").lower() == "true"


settings = Settings()