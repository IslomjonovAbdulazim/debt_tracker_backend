# Improved auth.py with fallback mechanisms and better performance

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
import socket
from concurrent.futures import ThreadPoolExecutor
import threading

from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, status, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

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

# Rate limiting storage (in production, use Redis)
email_rate_limit: Dict[str, Dict[str, Any]] = {}

# Email configuration constants
GMAIL_SMTP_SERVER = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587
EMAIL_TIMEOUT = 10  # Reduced timeout for faster failures
MAX_RETRIES = 2  # Reduced retries for faster response
RETRY_DELAY = 1  # Reduced retry delay

# Thread pool for background email sending
email_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="email_sender")

# In-memory storage for codes when email fails (simple fallback)
temp_codes: Dict[str, Dict[str, Any]] = {}


class EmailRateLimiter:
    """Simple rate limiter for email sending"""

    @staticmethod
    def is_rate_limited(email: str, limit: int = 5, window: int = 300) -> bool:
        """Check if email is rate limited (increased limit for better UX)"""
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
        """Reset rate limit for email"""
        if email in email_rate_limit:
            del email_rate_limit[email]


def check_network_connectivity() -> bool:
    """Quick check if we can reach Gmail SMTP"""
    try:
        # Try to connect to Gmail SMTP server
        sock = socket.create_connection((GMAIL_SMTP_SERVER, GMAIL_SMTP_PORT), timeout=3)
        sock.close()
        return True
    except (socket.error, socket.timeout):
        return False


def send_email_sync(to_email: str, subject: str, html_content: str) -> bool:
    """Synchronous email sending with quick failure"""

    # Check if email sending is disabled
    if getattr(settings, 'SKIP_EMAIL_SEND', False):
        logger.info(f"Email sending disabled. Would send: {subject} to {to_email}")
        return True

    # Validate email configuration
    if not all([settings.MAIL_USERNAME, settings.MAIL_PASSWORD, settings.MAIL_FROM]):
        logger.error("Email configuration incomplete")
        return False

    # Quick network check
    if not check_network_connectivity():
        logger.warning(f"Cannot reach Gmail SMTP server for {to_email}")
        return False

    try:
        logger.info(f"Sending email to {to_email}")

        # Create email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = formataddr((settings.APP_NAME, settings.MAIL_FROM))
        msg['To'] = to_email

        # Add HTML content
        html_part = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(html_part)

        # Create SSL context
        context = ssl.create_default_context()

        # Connect and send email with shorter timeout
        with smtplib.SMTP(GMAIL_SMTP_SERVER, GMAIL_SMTP_PORT, timeout=EMAIL_TIMEOUT) as server:
            server.starttls(context=context)
            server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            result = server.send_message(msg)

            if not result:
                logger.info(f"✅ Email sent successfully to {to_email}")
                return True
            else:
                logger.warning(f"Partial send failure: {result}")
                return False

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication failed: {e}")
        return False
    except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, socket.timeout, socket.error) as e:
        logger.warning(f"Network/SMTP error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected email error: {e}")
        return False


def send_email_background(to_email: str, subject: str, html_content: str):
    """Send email in background thread"""
    try:
        success = send_email_sync(to_email, subject, html_content)
        if success:
            logger.info(f"Background email sent to {to_email}")
        else:
            logger.warning(f"Background email failed for {to_email}")
    except Exception as e:
        logger.error(f"Background email error for {to_email}: {e}")


def store_temp_code(email: str, code: str, code_type: str, expiry_minutes: int = 10):
    """Store code temporarily when email fails"""
    expires_at = datetime.utcnow() + timedelta(minutes=expiry_minutes)
    temp_codes[email] = {
        "code": code,
        "code_type": code_type,
        "expires_at": expires_at,
        "created_at": datetime.utcnow()
    }
    logger.info(f"Stored temporary code for {email} (type: {code_type})")


def get_temp_code(email: str, code: str, code_type: str) -> bool:
    """Check if temp code is valid"""
    if email not in temp_codes:
        return False

    temp_data = temp_codes[email]
    if (temp_data["code"] == code and
            temp_data["code_type"] == code_type and
            temp_data["expires_at"] > datetime.utcnow()):
        # Code is valid, remove it
        del temp_codes[email]
        logger.info(f"Valid temporary code used for {email}")
        return True

    return False


def create_simple_email_template(name: str, code: str, action_type: str = "verification") -> str:
    """Create lightweight email template"""
    action_text = {
        "verification": "verify your email",
        "password_reset": "reset your password"
    }

    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #007bff; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0;">{settings.APP_NAME}</h1>
        </div>
        <div style="background: white; padding: 30px; border: 1px solid #ddd; border-radius: 0 0 8px 8px;">
            <h2>Hello {name}!</h2>
            <p>Your verification code to {action_text.get(action_type, action_type)} is:</p>
            <div style="font-size: 32px; font-weight: bold; color: #007bff; text-align: center; 
                        padding: 20px; background: #f8f9fa; border-radius: 8px; margin: 20px 0; 
                        letter-spacing: 4px; font-family: monospace;">
                {code}
            </div>
            <p><strong>This code expires in 10 minutes.</strong></p>
            <p>If you didn't request this, please ignore this email.</p>
            <hr style="margin: 20px 0; border: none; border-top: 1px solid #eee;">
            <p style="color: #666; font-size: 12px;">© 2025 {settings.APP_NAME}</p>
        </div>
    </div>
    """


# Password functions
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


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
def send_verification_email(email: str, name: str, code: str, background_tasks: BackgroundTasks = None) -> dict:
    """Send email verification code with fallback"""
    logger.info(f"Attempting to send verification email to {email}")

    # Check rate limiting
    if EmailRateLimiter.is_rate_limited(email):
        raise Exception("Too many email requests. Please wait before requesting again.")

    html_content = create_simple_email_template(name, code, "verification")
    subject = f"{settings.APP_NAME} - Verification Code"

    # Try to send email immediately (quick attempt)
    email_sent = send_email_sync(email, subject, html_content)

    if email_sent:
        return {
            "email_sent": True,
            "fallback_used": False,
            "message": "Verification code sent to your email"
        }

    # Email failed - store code as fallback
    store_temp_code(email, code, "email", 10)

    # Try sending in background
    if background_tasks:
        background_tasks.add_task(send_email_background, email, subject, html_content)

    # Return code in response when email fails (for mobile app)
    response_data = {
        "email_sent": False,
        "fallback_used": True,
        "message": "Email service unavailable. Please use the code below:",
        "temp_code_stored": True,
        "code_expires_in_minutes": 10,
        "note": "Email service is down. Use this code to verify your account."
    }

    # Only expose code if allowed by settings
    if settings.EXPOSE_CODES_ON_EMAIL_FAILURE and not (
            settings.HIDE_CODES_IN_PRODUCTION and settings.SERVER_ENVIRONMENT == "production"):
        response_data["verification_code"] = code
        response_data["show_code_to_user"] = True
    else:
        response_data["show_code_to_user"] = False
        response_data["contact_support"] = "Contact support for manual verification"

    return response_data


def send_password_reset_email(email: str, name: str, code: str, background_tasks: BackgroundTasks = None) -> dict:
    """Send password reset code with fallback"""
    logger.info(f"Attempting to send password reset email to {email}")

    html_content = create_simple_email_template(name, code, "password_reset")
    subject = f"{settings.APP_NAME} - Password Reset Code"

    # Try to send email immediately
    email_sent = send_email_sync(email, subject, html_content)

    if email_sent:
        return {
            "email_sent": True,
            "fallback_used": False,
            "message": "Reset code sent to your email"
        }

    # Email failed - store code as fallback
    store_temp_code(email, code, "password_reset", 15)

    # Try sending in background
    if background_tasks:
        background_tasks.add_task(send_email_background, email, subject, html_content)

    # Return code in response when email fails (for mobile app)
    response_data = {
        "email_sent": False,
        "fallback_used": True,
        "message": "Email service unavailable. Please use the code below:",
        "temp_code_stored": True,
        "code_expires_in_minutes": 15,
        "note": "Email service is down. Use this code to reset your password."
    }

    # Only expose code if allowed by settings
    if settings.EXPOSE_CODES_ON_EMAIL_FAILURE and not (
            settings.HIDE_CODES_IN_PRODUCTION and settings.SERVER_ENVIRONMENT == "production"):
        response_data["verification_code"] = code
        response_data["show_code_to_user"] = True
    else:
        response_data["show_code_to_user"] = False
        response_data["contact_support"] = "Contact support for manual verification"

    return response_data


# Enhanced verification that checks both DB and temp storage
def verify_code_with_fallback(email: str, code: str, code_type: str, db: Session) -> bool:
    """Verify code from database or temporary storage"""
    from app.database import VerificationCode

    # First check database
    code_record = db.query(VerificationCode).filter(
        VerificationCode.email == email,
        VerificationCode.code == code,
        VerificationCode.code_type == code_type,
        VerificationCode.used == False,
        VerificationCode.expires_at > datetime.utcnow()
    ).first()

    if code_record:
        code_record.used = True
        db.commit()
        logger.info(f"Code verified from database for {email}")
        return True

    # Check temporary storage as fallback
    if get_temp_code(email, code, code_type):
        logger.info(f"Code verified from temporary storage for {email}")
        return True

    return False


# Utility function to reset rate limits
def reset_email_rate_limit(email: str):
    """Reset rate limit for an email address"""
    EmailRateLimiter.reset_rate_limit(email)


# Email testing function (simplified)
def test_email_configuration() -> dict:
    """Test email configuration quickly"""
    if not all([settings.MAIL_USERNAME, settings.MAIL_PASSWORD, settings.MAIL_FROM]):
        return {"success": False, "message": "Email configuration incomplete"}

    if not check_network_connectivity():
        return {"success": False, "message": "Cannot reach Gmail SMTP server"}

    try:
        test_code = generate_code()
        html_content = create_simple_email_template("Test User", test_code, "verification")
        success = send_email_sync(settings.MAIL_USERNAME, f"{settings.APP_NAME} - Test", html_content)

        return {
            "success": success,
            "message": "Email test successful" if success else "Email test failed"
        }
    except Exception as e:
        return {"success": False, "message": f"Email test error: {str(e)}"}


# Cleanup function for temp codes (call periodically)
def cleanup_temp_codes():
    """Remove expired temporary codes"""
    now = datetime.utcnow()
    expired_emails = [
        email for email, data in temp_codes.items()
        if data["expires_at"] < now
    ]

    for email in expired_emails:
        del temp_codes[email]

    if expired_emails:
        logger.info(f"Cleaned up {len(expired_emails)} expired temporary codes")