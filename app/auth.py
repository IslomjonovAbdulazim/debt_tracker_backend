# Updated auth.py with automatic fallback system (try option 1, if fail try option 2, etc.)

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
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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


async def send_email_auto_fallback(subject: str, recipient: str, html_content: str):
    """
    Automatic fallback email system:
    Option 1: Gmail TLS port 587 (most common)
    Option 2: Gmail SSL port 465 (when 587 is blocked)
    Option 3: Gmail port 25 (backup)
    Option 4: Direct SMTP fallback
    Option 5: Log only (if all fail)
    """

    # Check if we should skip email entirely
    if os.getenv("SKIP_EMAIL_SEND", "False").lower() == "true":
        logger.warning(f"SKIP_EMAIL_SEND is True. Email skipped for {recipient}")
        return True

    # If no credentials, skip to logging
    if not settings.MAIL_USERNAME or not settings.MAIL_PASSWORD:
        logger.warning(f"No email credentials. Email content logged for {recipient}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Content: {html_content}")
        return True

    # Define email options in order of preference
    email_options = [
        # Option 1: Standard Gmail TLS (most reliable)
        {
            "name": "Gmail TLS 587",
            "method": "fastmail",
            "config": {
                "MAIL_PORT": 587,
                "MAIL_SERVER": "smtp.gmail.com",
                "MAIL_STARTTLS": True,
                "MAIL_SSL_TLS": False,
                "timeout": 10
            }
        },
        # Option 2: Gmail SSL (when TLS is blocked)
        {
            "name": "Gmail SSL 465",
            "method": "fastmail",
            "config": {
                "MAIL_PORT": 465,
                "MAIL_SERVER": "smtp.gmail.com",
                "MAIL_STARTTLS": False,
                "MAIL_SSL_TLS": True,
                "timeout": 10
            }
        },
        # Option 3: Alternative port (some servers use this)
        {
            "name": "Gmail Port 25",
            "method": "fastmail",
            "config": {
                "MAIL_PORT": 25,
                "MAIL_SERVER": "smtp.gmail.com",
                "MAIL_STARTTLS": True,
                "MAIL_SSL_TLS": False,
                "timeout": 10
            }
        },
        # Option 4: Direct SMTP TLS
        {
            "name": "Direct SMTP TLS",
            "method": "direct_smtp",
            "config": {"host": "smtp.gmail.com", "port": 587, "use_tls": True}
        },
        # Option 5: Direct SMTP SSL
        {
            "name": "Direct SMTP SSL",
            "method": "direct_smtp",
            "config": {"host": "smtp.gmail.com", "port": 465, "use_ssl": True}
        }
    ]

    # Try each option until one works
    for i, option in enumerate(email_options, 1):
        try:
            logger.info(f"Trying Option {i}: {option['name']}")

            if option["method"] == "fastmail":
                success = await try_fastmail(option, subject, recipient, html_content)
            else:
                success = await try_direct_smtp(option, subject, recipient, html_content)

            if success:
                logger.info(f"✅ Email sent successfully using Option {i}: {option['name']}")
                return True

        except Exception as e:
            logger.warning(f"❌ Option {i} ({option['name']}) failed: {str(e)}")
            continue

    # If all options fail, log the content for debugging
    logger.error("❌ All email sending options failed!")
    if settings.DEBUG:
        logger.info(f"DEBUG MODE - Email content for {recipient}:")
        logger.info(f"Subject: {subject}")
        logger.info(f"HTML Content: {html_content}")

    return False


async def try_fastmail(option, subject: str, recipient: str, html_content: str):
    """Try sending email using FastMail with specific configuration"""
    config = ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,
        MAIL_PASSWORD=settings.MAIL_PASSWORD,
        MAIL_FROM=settings.MAIL_FROM,
        MAIL_PORT=option["config"]["MAIL_PORT"],
        MAIL_SERVER=option["config"]["MAIL_SERVER"],
        MAIL_STARTTLS=option["config"]["MAIL_STARTTLS"],
        MAIL_SSL_TLS=option["config"]["MAIL_SSL_TLS"],
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=False,
        MAIL_FROM_NAME=settings.APP_NAME,
        TIMEOUT=option["config"]["timeout"]
    )

    fastmail = FastMail(config)
    message = MessageSchema(
        subject=subject,
        recipients=[recipient],
        body=html_content,
        subtype=MessageType.html
    )

    # Send with timeout
    await asyncio.wait_for(fastmail.send_message(message), timeout=15.0)
    return True


async def try_direct_smtp(option, subject: str, recipient: str, html_content: str):
    """Try sending email using direct SMTP"""
    config = option["config"]

    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = settings.MAIL_FROM or settings.MAIL_USERNAME
    msg['To'] = recipient

    # Add HTML part
    html_part = MIMEText(html_content, 'html')
    msg.attach(html_part)

    # Connect and send
    if config.get("use_ssl"):
        server = smtplib.SMTP_SSL(config['host'], config['port'], timeout=10)
    else:
        server = smtplib.SMTP(config['host'], config['port'], timeout=10)
        if config.get("use_tls"):
            server.starttls()

    server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
    server.send_message(msg)
    server.quit()
    return True


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


# Simplified email functions
async def send_verification_email(email: str, name: str, code: str):
    """Send email verification code with automatic fallback"""
    logger.info(f"Sending verification email to {email}")

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

    success = await send_email_auto_fallback(
        subject=f"{settings.APP_NAME} - Email Verification",
        recipient=email,
        html_content=html_content
    )

    if not success:
        logger.error(f"Failed to send verification email to {email}")
        if settings.DEBUG:
            logger.info(f"DEBUG MODE - Verification code for {email}: {code}")
        raise Exception("Email sending failed after trying all methods")


async def send_password_reset_email(email: str, name: str, code: str):
    """Send password reset code with automatic fallback"""
    logger.info(f"Sending password reset email to {email}")

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

    success = await send_email_auto_fallback(
        subject=f"{settings.APP_NAME} - Password Reset",
        recipient=email,
        html_content=html_content
    )

    if not success:
        logger.error(f"Failed to send password reset email to {email}")
        if settings.DEBUG:
            logger.info(f"DEBUG MODE - Password reset code for {email}: {code}")
        raise Exception("Email sending failed after trying all methods")


# Test function
async def test_email_configuration():
    """Test the automatic fallback email system"""
    logger.info("Testing automatic email fallback system...")

    try:
        success = await send_email_auto_fallback(
            subject="Test Email - Auto Fallback System",
            recipient=settings.MAIL_USERNAME,  # Send to self
            html_content="""
            <div style="font-family: Arial, sans-serif;">
                <h2>✅ Email Test Successful!</h2>
                <p>This email was sent using the automatic fallback system.</p>
                <p>Your email configuration is working correctly!</p>
            </div>
            """
        )

        if success:
            return ["✅ Auto-fallback email system is working!"]
        else:
            return ["❌ All email methods failed in auto-fallback system"]

    except Exception as e:
        return [f"❌ Email test failed: {str(e)}"]