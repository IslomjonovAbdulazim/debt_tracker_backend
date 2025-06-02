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

    # Email Features
    SKIP_EMAIL_SEND: bool = os.getenv("SKIP_EMAIL_SEND", "False").lower() == "true"
    EMAIL_RATE_LIMIT: int = int(os.getenv("EMAIL_RATE_LIMIT", "3"))  # emails per window
    EMAIL_RATE_WINDOW: int = int(os.getenv("EMAIL_RATE_WINDOW", "300"))  # seconds (5 min)

    # OTP Settings
    EMAIL_VERIFICATION_EXPIRY: int = int(os.getenv("EMAIL_VERIFICATION_EXPIRY", "10"))  # minutes
    PASSWORD_RESET_EXPIRY: int = int(os.getenv("PASSWORD_RESET_EXPIRY", "15"))  # minutes

    # App
    APP_NAME: str = os.getenv("APP_NAME", "Debt Tracker API")
    APP_VERSION: str = os.getenv("APP_VERSION", "2.0.0")

    # Server Configuration
    SERVER_ENVIRONMENT: str = os.getenv("SERVER_ENVIRONMENT", "development")  # development, staging, production

    # External Email Services (Optional - for production)
    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    MAILGUN_API_KEY: str = os.getenv("MAILGUN_API_KEY", "")
    MAILGUN_DOMAIN: str = os.getenv("MAILGUN_DOMAIN", "")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")


settings = Settings()