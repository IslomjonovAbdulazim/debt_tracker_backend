# Updated auth.py with multiple email configuration options

import random
import string
from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from sqlalchemy.orm import Session
import logging
import os

from app.config import settings
from app.database import get_db, User
from app.responses import error_response

# Set up logging
logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# Security scheme
security = HTTPBearer()


# Email configuration with multiple options
def get_mail_config():
    """Get email configuration based on environment"""

    # Check if we should use alternative ports
    mail_port = int(os.getenv("MAIL_PORT", "587"))
    mail_server = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    use_tls = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
    use_ssl = os.getenv("MAIL_USE_SSL", "False").lower() == "true"

    # Try different configurations based on environment
    if os.getenv("USE_SMTP_SSL", "False").lower() == "true":
        # Option 1: SSL/TLS on port 465 (often works when 587 is blocked)
        mail_config = ConnectionConfig(
            MAIL_USERNAME=settings.MAIL_USERNAME,
            MAIL_PASSWORD=settings.MAIL_PASSWORD,
            MAIL_FROM=settings.MAIL_FROM,
            MAIL_PORT=465,
            MAIL_SERVER="smtp.gmail.com",
            MAIL_STARTTLS=False,
            MAIL_SSL_TLS=True,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True,
            MAIL_FROM_NAME=settings.APP_NAME
        )
    else:
        # Option 2: Standard TLS on port 587
        mail_config = ConnectionConfig(
            MAIL_USERNAME=settings.MAIL_USERNAME,
            MAIL_PASSWORD=settings.MAIL_PASSWORD,
            MAIL_FROM=settings.MAIL_FROM,
            MAIL_PORT=mail_port,
            MAIL_SERVER=mail_server,
            MAIL_STARTTLS=use_tls,
            MAIL_SSL_TLS=use_ssl,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=False,
            MAIL_FROM_NAME=settings.APP_NAME,
            TIMEOUT=30  # Increase timeout
        )

    return mail_config


# Initialize FastMail with configuration
mail_config = get_mail_config()
fastmail = FastMail(mail_config)


# Password functions
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def generate_code() -> str:
    return ''.join(random.choices(string.digits, k=6))


# JWT functions
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise JWTError("Invalid token")
        return {"user_id": int(user_id)}
    except JWTError:
        error_response("Invalid or expired token", status_code=status.HTTP_401_UNAUTHORIZED)


# Authentication dependency
def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db)
) -> User:
    token_data = verify_token(credentials.credentials)
    user = db.query(User).filter(User.id == token_data["user_id"]).first()

    if not user:
        error_response("User not found", status_code=status.HTTP_401_UNAUTHORIZED)

    if not user.is_verified:
        error_response("Email not verified", status_code=status.HTTP_403_FORBIDDEN)

    return user


# Email functions with fallback options
async def send_verification_email(email: str, name: str, code: str):
    """Send email verification code"""
    logger.info(f"Attempting to send verification email to {email}")

    # Check if we should skip email in development
    if os.getenv("SKIP_EMAIL_SEND", "False").lower() == "true":
        logger.warning(f"SKIP_EMAIL_SEND is True. Verification code for {email}: {code}")
        return

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #333;">Email Verification</h2>
        <p>Hello {name},</p>
        <p>Your verification code is:</p>
        <div style="background: #f0f0f0; padding: 20px; text-align: center; font-size: 24px; font-weight: bold; margin: 20px 0;">
            {code}
        </div>
        <p>This code expires in 10 minutes.</p>
        <p>If you didn't request this, please ignore this email.</p>
        <p>Best regards,<br>{settings.APP_NAME}</p>
    </div>
    """

    try:
        message = MessageSchema(
            subject=f"{settings.APP_NAME} - Email Verification",
            recipients=[email],
            body=html_content,
            subtype=MessageType.html
        )

        await fastmail.send_message(message)
        logger.info(f"Verification email sent successfully to {email}")
    except Exception as e:
        logger.error(f"Failed to send verification email to {email}: {str(e)}")

        # Log the verification code in development mode
        if settings.DEBUG:
            logger.info(f"DEBUG MODE - Verification code for {email}: {code}")

        raise


async def send_password_reset_email(email: str, name: str, code: str):
    """Send password reset code"""
    logger.info(f"Attempting to send password reset email to {email}")

    # Check if we should skip email in development
    if os.getenv("SKIP_EMAIL_SEND", "False").lower() == "true":
        logger.warning(f"SKIP_EMAIL_SEND is True. Password reset code for {email}: {code}")
        return

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #333;">Password Reset</h2>
        <p>Hello {name},</p>
        <p>Your password reset code is:</p>
        <div style="background: #f0f0f0; padding: 20px; text-align: center; font-size: 24px; font-weight: bold; margin: 20px 0;">
            {code}
        </div>
        <p>This code expires in 15 minutes.</p>
        <p>If you didn't request this, please ignore this email.</p>
        <p>Best regards,<br>{settings.APP_NAME}</p>
    </div>
    """

    try:
        message = MessageSchema(
            subject=f"{settings.APP_NAME} - Password Reset",
            recipients=[email],
            body=html_content,
            subtype=MessageType.html
        )

        await fastmail.send_message(message)
        logger.info(f"Password reset email sent successfully to {email}")
    except Exception as e:
        logger.error(f"Failed to send password reset email to {email}: {str(e)}")

        # Log the reset code in development mode
        if settings.DEBUG:
            logger.info(f"DEBUG MODE - Password reset code for {email}: {code}")

        raise