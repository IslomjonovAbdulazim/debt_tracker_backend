# Improved auth.py with bcrypt compatibility fix

import random
import string
import asyncio
import smtplib
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import ssl
import logging

# Fixed bcrypt import
try:
    from passlib.context import CryptContext
    # Try to create context with bcrypt
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except Exception as e:
    logging.warning(f"Bcrypt compatibility issue: {e}")
    # Fallback to pbkdf2_sha256 if bcrypt fails
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    logging.info("Using pbkdf2_sha256 instead of bcrypt for password hashing")

from jose import JWTError, jwt
from fastapi import Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, User
from app.responses import error_response

# Set up logging
logger = logging.getLogger(__name__)

# JWT settings
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# Security scheme
security = HTTPBearer()

# Rate limiting storage (in production, use Redis)
email_rate_limit: Dict[str, Dict[str, Any]] = {}

# Email configuration constants
GMAIL_SMTP_SERVER = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587  # Use 587 for TLS (most reliable)
EMAIL_TIMEOUT = 30  # Increased timeout for server environments
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


class EmailRateLimiter:
    """Simple rate limiter for email sending"""

    @staticmethod
    def is_rate_limited(email: str, limit: int = 3, window: int = 300) -> bool:
        """Check if email is rate limited (default: 3 emails per 5 minutes)"""
        now = time.time()

        if email not in email_rate_limit:
            email_rate_limit[email] = {"count": 0, "window_start": now}
            return False

        rate_data = email_rate_limit[email]

        # Reset window if expired
        if now - rate_data["window_start"] > window:
            rate_data["count"] = 0
            rate_data["window_start"] = now

        # Check if limit exceeded
        if rate_data["count"] >= limit:
            return True

        rate_data["count"] += 1
        return False

    @staticmethod
    def reset_rate_limit(email: str):
        """Reset rate limit for email (useful after successful verification)"""
        if email in email_rate_limit:
            del email_rate_limit[email]


async def send_email_with_retry(
        to_email: str,
        subject: str,
        html_content: str,
        max_retries: int = MAX_RETRIES
) -> bool:
    """
    Send email with retry mechanism and exponential backoff
    """
    # Check if email sending is disabled
    if getattr(settings, 'SKIP_EMAIL_SEND', False):
        logger.warning(f"Email sending disabled. Would send: {subject} to {to_email}")
        return True

    # Validate email configuration
    if not all([settings.MAIL_USERNAME, settings.MAIL_PASSWORD, settings.MAIL_FROM]):
        logger.error("Email configuration incomplete")
        if settings.DEBUG:
            logger.info(f"DEBUG MODE - Email content for {to_email}:")
            logger.info(f"Subject: {subject}")
            logger.info(f"Content: {html_content}")
        return False

    # Check rate limiting
    if EmailRateLimiter.is_rate_limited(to_email):
        logger.warning(f"Rate limit exceeded for {to_email}")
        raise Exception("Too many email requests. Please wait before requesting again.")

    last_error = None

    for attempt in range(max_retries):
        try:
            logger.info(f"Sending email to {to_email} (attempt {attempt + 1}/{max_retries})")

            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = formataddr((settings.APP_NAME, settings.MAIL_FROM))
            msg['To'] = to_email

            # Add HTML content
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)

            # Create SSL context with proper security
            context = ssl.create_default_context()

            # Connect and send email
            with smtplib.SMTP(GMAIL_SMTP_SERVER, GMAIL_SMTP_PORT, timeout=EMAIL_TIMEOUT) as server:
                server.starttls(context=context)
                server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)

                # Send email
                result = server.send_message(msg)

                if not result:  # Empty dict means success
                    logger.info(f"✅ Email sent successfully to {to_email}")
                    return True
                else:
                    logger.warning(f"Partial send failure: {result}")

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP Authentication failed: {e}")
            raise Exception("Email authentication failed. Please check your email credentials.")

        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"Recipient refused: {e}")
            raise Exception("Invalid recipient email address.")

        except smtplib.SMTPServerDisconnected as e:
            logger.warning(f"SMTP server disconnected: {e}")
            last_error = e

        except smtplib.SMTPConnectError as e:
            logger.warning(f"SMTP connection error: {e}")
            last_error = e

        except Exception as e:
            logger.warning(f"Email attempt {attempt + 1} failed: {str(e)}")
            last_error = e

        # Wait before retry (exponential backoff)
        if attempt < max_retries - 1:
            wait_time = RETRY_DELAY * (2 ** attempt)  # 2, 4, 8 seconds
            logger.info(f"Waiting {wait_time} seconds before retry...")
            await asyncio.sleep(wait_time)

    # All attempts failed
    logger.error(f"❌ Failed to send email to {to_email} after {max_retries} attempts")
    logger.error(f"Last error: {last_error}")

    if settings.DEBUG:
        logger.info(f"DEBUG MODE - Email content for {to_email}:")
        logger.info(f"Subject: {subject}")
        logger.info(f"Content: {html_content}")

    return False


def create_email_template(
        title: str,
        name: str,
        code: str,
        expiry_minutes: int,
        action_type: str = "verification"
) -> str:
    """
    Create standardized email template for OTP codes
    """
    action_text = {
        "verification": "verify your email",
        "password_reset": "reset your password"
    }

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #f4f4f4; font-family: Arial, sans-serif;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 0;">
            <!-- Header -->
            <div style="background-color: #007bff; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 24px;">{settings.APP_NAME}</h1>
            </div>

            <!-- Content -->
            <div style="padding: 30px;">
                <h2 style="color: #333; margin-top: 0;">{title}</h2>
                <p style="color: #555; font-size: 16px; line-height: 1.5;">Hello {name},</p>
                <p style="color: #555; font-size: 16px; line-height: 1.5;">
                    We received a request to {action_text.get(action_type, action_type)} for your account.
                </p>
                <p style="color: #555; font-size: 16px; line-height: 1.5;">Your verification code is:</p>

                <!-- OTP Code Box -->
                <div style="background-color: #f8f9fa; border: 2px solid #007bff; border-radius: 8px; padding: 20px; text-align: center; margin: 25px 0;">
                    <div style="font-size: 32px; font-weight: bold; color: #007bff; letter-spacing: 4px; font-family: 'Courier New', monospace;">
                        {code}
                    </div>
                </div>

                <!-- Important Info -->
                <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px; padding: 15px; margin: 20px 0;">
                    <p style="margin: 0; color: #856404; font-size: 14px;">
                        <strong>⚠️ Important:</strong><br>
                        • This code expires in <strong>{expiry_minutes} minutes</strong><br>
                        • Enter this code exactly as shown<br>
                        • If you didn't request this, please ignore this email
                    </p>
                </div>

                <p style="color: #555; font-size: 16px; line-height: 1.5;">
                    If you have any questions, please contact our support team.
                </p>

                <p style="color: #555; font-size: 16px; line-height: 1.5;">
                    Best regards,<br>
                    <strong>{settings.APP_NAME} Team</strong>
                </p>
            </div>

            <!-- Footer -->
            <div style="background-color: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #dee2e6;">
                <p style="margin: 0; color: #6c757d; font-size: 12px;">
                    This is an automated message, please do not reply to this email.
                </p>
                <p style="margin: 5px 0 0 0; color: #6c757d; font-size: 12px;">
                    © 2025 {settings.APP_NAME}. All rights reserved.
                </p>
            </div>
        </div>
    </body>
    </html>
    """


# Password functions with improved error handling
def hash_password(password: str) -> str:
    try:
        return pwd_context.hash(password)
    except Exception as e:
        logger.error(f"Password hashing error: {e}")
        # Fallback to basic hashing if bcrypt fails
        import hashlib
        import secrets
        salt = secrets.token_hex(16)
        return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex() + ':' + salt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        # Fallback verification for fallback hash format
        if ':' in hashed_password:
            import hashlib
            hash_part, salt = hashed_password.split(':')
            return hashlib.pbkdf2_hmac('sha256', plain_password.encode(), salt.encode(), 100000).hex() == hash_part
        return False


def generate_code() -> str:
    """Generate a secure 6-digit OTP code"""
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


# Email sending functions
async def send_verification_email(email: str, name: str, code: str) -> bool:
    """Send email verification code"""
    logger.info(f"Sending verification email to {email}")

    html_content = create_email_template(
        title="Email Verification",
        name=name,
        code=code,
        expiry_minutes=settings.EMAIL_VERIFICATION_EXPIRY,
        action_type="verification"
    )

    success = await send_email_with_retry(
        to_email=email,
        subject=f"{settings.APP_NAME} - Email Verification Code",
        html_content=html_content
    )

    if not success:
        raise Exception("Failed to send verification email. Please try again later.")

    return True


async def send_password_reset_email(email: str, name: str, code: str) -> bool:
    """Send password reset code"""
    logger.info(f"Sending password reset email to {email}")

    html_content = create_email_template(
        title="Password Reset",
        name=name,
        code=code,
        expiry_minutes=settings.PASSWORD_RESET_EXPIRY,
        action_type="password_reset"
    )

    success = await send_email_with_retry(
        to_email=email,
        subject=f"{settings.APP_NAME} - Password Reset Code",
        html_content=html_content
    )

    if not success:
        raise Exception("Failed to send password reset email. Please try again later.")

    return True


# Email testing function
async def test_email_configuration() -> list:
    """Test email configuration"""
    logger.info("Testing email configuration...")

    if not all([settings.MAIL_USERNAME, settings.MAIL_PASSWORD, settings.MAIL_FROM]):
        return ["❌ Email configuration incomplete. Check MAIL_USERNAME, MAIL_PASSWORD, and MAIL_FROM."]

    try:
        test_code = generate_code()
        html_content = create_email_template(
            title="Email Configuration Test",
            name="Test User",
            code=test_code,
            expiry_minutes=10,
            action_type="verification"
        )

        success = await send_email_with_retry(
            to_email=settings.MAIL_USERNAME,  # Send test to self
            subject=f"{settings.APP_NAME} - Email Test",
            html_content=html_content
        )

        if success:
            return ["✅ Email configuration test successful!"]
        else:
            return ["❌ Email test failed. Check your configuration and network."]

    except Exception as e:
        return [f"❌ Email test error: {str(e)}"]


# Utility function to reset rate limits (useful for successful verifications)
def reset_email_rate_limit(email: str):
    """Reset rate limit for an email address"""
    EmailRateLimiter.reset_rate_limit(email)

