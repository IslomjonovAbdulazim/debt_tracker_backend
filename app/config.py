# app/config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./debt_tracker.db"
    )

    # Email Configuration
    MAIL_USERNAME: str = os.getenv("MAIL_USERNAME", "islomjonov.abdulazim.27@gmail.com")
    MAIL_PASSWORD: str = os.getenv("MAIL_PASSWORD", "pkaluadtivormjjl")
    MAIL_FROM: str = os.getenv("MAIL_FROM", "islomjonov.abdulazim.27@gmail.com")

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-this")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # App Settings
    APP_NAME: str = "Debt Tracker API"
    APP_VERSION: str = "1.0.0"

    # OAuth Settings
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    API_URL: str = os.getenv("API_URL", "http://localhost:8000")

    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = f"{API_URL}/auth/google/callback"

    # GitHub OAuth
    GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET", "")
    GITHUB_REDIRECT_URI: str = f"{API_URL}/auth/github/callback"


# Create settings instance
settings = Settings()