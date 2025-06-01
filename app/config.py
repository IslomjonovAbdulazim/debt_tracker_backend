import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./debt_tracker.db")

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"

    # Email
    MAIL_USERNAME: str = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD: str = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM: str = os.getenv("MAIL_FROM", "")

    # App
    APP_NAME: str = os.getenv("APP_NAME", "Debt Tracker API")
    APP_VERSION: str = os.getenv("APP_VERSION", "2.0.0")


settings = Settings()