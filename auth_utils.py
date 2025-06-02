from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import json
import asyncio
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import socket
import ssl
from email.utils import formataddr

# Load environment variables
load_dotenv()

# Configuration with 2025 best practices
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# Gmail SMTP Configuration (2025 Standards)
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")  # App password, not regular password
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "True").lower() == "true"
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "False").lower() == "true"
SMTP_TIMEOUT = int(os.getenv("SMTP_TIMEOUT", "30"))

# Email settings
APP_NAME = os.getenv("APP_NAME", "Simple Debt Tracker")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", APP_NAME)
EMAIL_RATE_LIMIT = int(os.getenv("EMAIL_RATE_LIMIT", "450"))
EMAIL_QUEUE_ENABLED = os.getenv("EMAIL_QUEUE_ENABLED", "True").lower() == "true"
EMAIL_RETRY_ATTEMPTS = int(os.getenv("EMAIL_RETRY_ATTEMPTS", "3"))
EMAIL_RETRY_DELAY = int(os.getenv("EMAIL_RETRY_DELAY", "5"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Enhanced logging for production
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rate limiting tracker
email_send_tracker = {
    "count": 0,
    "reset_time": datetime.utcnow() + timedelta(days=1)
}


# ==================
# PASSWORD FUNCTIONS
# ==================

def hash_password(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password"""
    return pwd_context.verify(plain_password, hashed_password)


# ==================
# JWT TOKEN FUNCTIONS
# ==================

def create_access_token(data: dict) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise JWTError("Invalid token")
        return {"user_id": int(user_id)}
    except JWTError:
        raise Exception("Invalid token")


# ==================
# EMAIL FUNCTIONS (2025 OPTIMIZED)
# ==================

def generate_code() -> str:
    """Generate 6-digit verification code"""
    return ''.join(random.choices(string.digits, k=6))


def create_email_template(name: str, code: str, action: str = "verify") -> str:
    """Create professional email template with 2025 design"""
    action_text = "verify your email" if action == "verify" else "reset your password"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{APP_NAME} - Email Verification</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f4;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 0;">
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 600;">{APP_NAME}</h1>
            </div>

            <!-- Content -->
            <div style="padding: 40px 30px;">
                <h2 style="color: #333; margin: 0 0 20px; font-size: 24px; font-weight: 600;">Hello {name}!</h2>
                <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 30px;">
                    We received a request to {action_text}. Use the verification code below to complete the process:
                </p>

                <!-- Code Box -->
                <div style="background: #f8f9fa; border: 2px dashed #007bff; border-radius: 10px; padding: 30px; text-align: center; margin: 30px 0;">
                    <div style="font-size: 36px; font-weight: bold; color: #007bff; letter-spacing: 8px; font-family: 'Courier New', monospace;">
                        {code}
                    </div>
                </div>

                <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 30px 0; border-radius: 5px;">
                    <p style="margin: 0; color: #856404; font-weight: 600;">⏰ This code expires in 10 minutes</p>
                </div>

                <p style="color: #6c757d; font-size: 14px; line-height: 1.5; margin: 30px 0 0;">
                    If you didn't request this verification, please ignore this email. Your account remains secure.
                </p>
            </div>

            <!-- Footer -->
            <div style="background: #f8f9fa; padding: 20px 30px; border-top: 1px solid #e9ecef;">
                <p style="margin: 0; color: #6c757d; font-size: 12px; text-align: center;">
                    © 2025 {APP_NAME}. This is an automated message, please do not reply.
                </p>
            </div>
        </div>
    </body>
    </html>
    """


def check_rate_limit() -> bool:
    """Check if we're within email sending rate limits"""
    global email_send_tracker

    now = datetime.utcnow()

    # Reset counter if 24 hours have passed
    if now >= email_send_tracker["reset_time"]:
        email_send_tracker = {
            "count": 0,
            "reset_time": now + timedelta(days=1)
        }

    # Check if we're under the limit
    if email_send_tracker["count"] >= EMAIL_RATE_LIMIT:
        logger.warning(f"Email rate limit exceeded: {email_send_tracker['count']}/{EMAIL_RATE_LIMIT}")
        return False

    return True


def increment_email_counter():
    """Increment email send counter"""
    global email_send_tracker
    email_send_tracker["count"] += 1
    logger.info(f"Email sent. Count: {email_send_tracker['count']}/{EMAIL_RATE_LIMIT}")


def validate_smtp_config() -> Dict[str, Any]:
    """Validate SMTP configuration"""
    errors = []

    if not GMAIL_USER:
        errors.append("GMAIL_USER is not configured")

    if not GMAIL_APP_PASSWORD:
        errors.append("GMAIL_APP_PASSWORD is not configured - you need a Gmail App Password")

    if GMAIL_APP_PASSWORD and len(GMAIL_APP_PASSWORD) != 16:
        errors.append("GMAIL_APP_PASSWORD should be 16 characters (Gmail App Password format)")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "config": {
            "server": SMTP_SERVER,
            "port": SMTP_PORT,
            "use_tls": SMTP_USE_TLS,
            "use_ssl": SMTP_USE_SSL,
            "timeout": SMTP_TIMEOUT,
            "user_configured": bool(GMAIL_USER),
            "password_configured": bool(GMAIL_APP_PASSWORD)
        }
    }


def create_smtp_connection() -> smtplib.SMTP:
    """Create and configure SMTP connection with 2025 best practices"""
    try:
        # Validate configuration first
        config_check = validate_smtp_config()
        if not config_check["valid"]:
            raise Exception(f"SMTP configuration errors: {', '.join(config_check['errors'])}")

        logger.info(f"Connecting to SMTP server: {SMTP_SERVER}:{SMTP_PORT}")

        # Create connection with timeout
        if SMTP_USE_SSL:
            # SSL connection (port 465)
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=SMTP_TIMEOUT, context=context)
        else:
            # TLS connection (port 587) - recommended
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=SMTP_TIMEOUT)

            if SMTP_USE_TLS:
                server.starttls()

        # Enable debug for development
        if os.getenv("DEBUG", "False").lower() == "true":
            server.set_debuglevel(1)

        # Authenticate with App Password
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        logger.info("SMTP authentication successful")

        return server

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication failed: {e}")
        logger.error(
            "Please check: 1) 2FA is enabled 2) Using App Password (not regular password) 3) App Password is correct")
        raise Exception("Gmail authentication failed - check your App Password configuration")
    except smtplib.SMTPConnectError as e:
        logger.error(f"SMTP Connection failed: {e}")
        raise Exception("Cannot connect to Gmail SMTP server")
    except socket.timeout:
        logger.error("SMTP connection timeout")
        raise Exception("SMTP connection timeout - check network connectivity")
    except Exception as e:
        logger.error(f"SMTP connection error: {e}")
        raise


def send_email_smtp(to_email: str, subject: str, body: str) -> bool:
    """Send email using Gmail SMTP with 2025 best practices"""
    try:
        # Check rate limits
        if not check_rate_limit():
            raise Exception("Daily email rate limit exceeded")

        # Create SMTP connection
        server = create_smtp_connection()

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = formataddr((EMAIL_FROM_NAME, GMAIL_USER))
            msg['To'] = to_email

            # Add HTML content
            html_part = MIMEText(body, 'html', 'utf-8')
            msg.attach(html_part)

            # Send email
            server.send_message(msg)
            increment_email_counter()

            logger.info(f"Email sent successfully to {to_email}")
            return True

        finally:
            # Always close connection
            server.quit()

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


async def send_email_with_fallback(to_email: str, subject: str, body: str) -> Dict[str, Any]:
    """Send email with async handling and fallback queue"""
    try:
        # Try to send email with timeout
        loop = asyncio.get_event_loop()
        success = await asyncio.wait_for(
            loop.run_in_executor(None, send_email_smtp, to_email, subject, body),
            timeout=SMTP_TIMEOUT + 5
        )

        if success:
            return {
                "email_sent": True,
                "method": "smtp",
                "message": "Email sent successfully via SMTP"
            }
        else:
            raise Exception("SMTP send failed")

    except asyncio.TimeoutError:
        logger.warning(f"Email timeout for {to_email}")
        if EMAIL_QUEUE_ENABLED:
            return await save_email_to_queue(to_email, subject, body, "timeout")
        else:
            return {"email_sent": False, "method": "failed", "message": "Email timeout"}
    except Exception as e:
        logger.error(f"Email error for {to_email}: {e}")
        if EMAIL_QUEUE_ENABLED:
            return await save_email_to_queue(to_email, subject, body, str(e))
        else:
            return {"email_sent": False, "method": "failed", "message": str(e)}


async def save_email_to_queue(to_email: str, subject: str, body: str, error: str) -> Dict[str, Any]:
    """Save email to queue when sending fails"""
    try:
        email_data = {
            "to": to_email,
            "subject": subject,
            "body": body,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
            "retry_count": 0,
            "max_retries": EMAIL_RETRY_ATTEMPTS
        }

        # Load existing queue
        queue_file = "email_queue.json"
        try:
            with open(queue_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                queue = json.loads(content) if content else []
        except (FileNotFoundError, json.JSONDecodeError):
            queue = []

        # Add new email
        queue.append(email_data)

        # Save queue
        with open(queue_file, 'w', encoding='utf-8') as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)

        logger.info(f"Email queued for {to_email}")
        return {
            "email_sent": True,
            "method": "queue",
            "message": "Email queued for delivery"
        }

    except Exception as e:
        logger.error(f"Failed to save email to queue: {e}")
        return {
            "email_sent": False,
            "method": "failed",
            "message": "Email delivery completely failed"
        }


async def send_verification_email(email: str, name: str, code: str) -> Dict[str, Any]:
    """Send verification email with fallback"""
    subject = f"{APP_NAME} - Verify Your Email"
    body = create_email_template(name, code, "verify")
    return await send_email_with_fallback(email, subject, body)


async def send_password_reset_email(email: str, name: str, code: str) -> Dict[str, Any]:
    """Send password reset email with fallback"""
    subject = f"{APP_NAME} - Reset Your Password"
    body = create_email_template(name, code, "reset")
    return await send_email_with_fallback(email, subject, body)


def test_smtp_connection() -> Dict[str, Any]:
    """Test SMTP connection and configuration"""
    try:
        config_check = validate_smtp_config()
        if not config_check["valid"]:
            return {
                "success": False,
                "message": "Configuration invalid",
                "errors": config_check["errors"]
            }

        # Test connection
        server = create_smtp_connection()
        server.quit()

        return {
            "success": True,
            "message": "SMTP connection successful",
            "config": config_check["config"]
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"SMTP connection failed: {str(e)}",
            "config": validate_smtp_config()["config"]
        }


def retry_queued_emails() -> Dict[str, Any]:
    """Retry sending queued emails"""
    try:
        with open("email_queue.json", 'r', encoding='utf-8') as f:
            content = f.read().strip()
            queue = json.loads(content) if content else []
    except (FileNotFoundError, json.JSONDecodeError):
        return {"processed": 0, "sent": 0, "failed": 0, "remaining": 0}

    sent = 0
    failed = 0
    remaining_queue = []

    for email_data in queue:
        try:
            # Check if we're still under rate limit
            if not check_rate_limit():
                remaining_queue.append(email_data)
                continue

            success = send_email_smtp(
                email_data["to"],
                email_data["subject"],
                email_data["body"]
            )

            if success:
                sent += 1
                logger.info(f"Queued email sent to {email_data['to']}")
            else:
                raise Exception("Send failed")

        except Exception as e:
            email_data["retry_count"] = email_data.get("retry_count", 0) + 1
            email_data["last_error"] = str(e)

            if email_data["retry_count"] < email_data.get("max_retries", EMAIL_RETRY_ATTEMPTS):
                remaining_queue.append(email_data)
            else:
                logger.error(f"Email permanently failed for {email_data['to']}: {e}")

            failed += 1

    # Save remaining queue
    try:
        with open("email_queue.json", 'w', encoding='utf-8') as f:
            json.dump(remaining_queue, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save email queue: {e}")

    return {
        "processed": len(queue),
        "sent": sent,
        "failed": failed,
        "remaining": len(remaining_queue)
    }