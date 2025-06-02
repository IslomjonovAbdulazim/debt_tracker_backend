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
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# Email configuration
EMAIL_SERVICE = os.getenv("EMAIL_SERVICE", "gmail")
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD", "")
APP_NAME = os.getenv("APP_NAME", "Simple Debt Tracker")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
# EMAIL FUNCTIONS (OPTIMIZED)
# ==================

def generate_code() -> str:
    """Generate 6-digit verification code"""
    return ''.join(random.choices(string.digits, k=6))


def create_email_template(name: str, code: str, action: str = "verify") -> str:
    """Create simple email template"""
    action_text = "verify your email" if action == "verify" else "reset your password"

    return f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; max-width: 500px;">
        <h2>{APP_NAME}</h2>
        <p>Hi {name},</p>
        <p>Your code to {action_text}:</p>
        <h1 style="color: #007bff; text-align: center; padding: 15px; background: #f8f9fa; border-radius: 5px;">
            {code}
        </h1>
        <p><strong>Expires in 10 minutes</strong></p>
        <p style="color: #666; font-size: 12px;">If you didn't request this, ignore this email.</p>
    </div>
    """


def send_email_gmail_sync(to_email: str, subject: str, body: str) -> bool:
    """Send email using Gmail SMTP (synchronous)"""
    try:
        if not GMAIL_USER or not GMAIL_PASSWORD:
            logger.error("Gmail credentials not configured")
            return False

        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = GMAIL_USER
        msg['To'] = to_email

        # Add HTML content
        html_part = MIMEText(body, 'html', 'utf-8')
        msg.attach(html_part)

        # Send email with timeout
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=10) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.send_message(msg)

        logger.info(f"Email sent successfully to {to_email}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"Gmail authentication failed: {e}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"Gmail SMTP error: {e}")
        return False
    except Exception as e:
        logger.error(f"Gmail error: {e}")
        return False


async def send_email_with_fallback(to_email: str, subject: str, body: str) -> dict:
    """Send email with timeout and fallback to queue"""
    try:
        # Try to send email with timeout
        loop = asyncio.get_event_loop()
        success = await asyncio.wait_for(
            loop.run_in_executor(None, send_email_gmail_sync, to_email, subject, body),
            timeout=8.0  # 8 second timeout
        )

        if success:
            return {
                "email_sent": True,
                "method": "email",
                "message": "Email sent successfully"
            }
        else:
            raise Exception("SMTP send failed")

    except asyncio.TimeoutError:
        logger.warning(f"Email timeout for {to_email}")
        return await save_email_to_queue(to_email, subject, body, "timeout")
    except Exception as e:
        logger.error(f"Email error for {to_email}: {e}")
        return await save_email_to_queue(to_email, subject, body, str(e))


async def save_email_to_queue(to_email: str, subject: str, body: str, error: str) -> dict:
    """Save email to queue when sending fails"""
    try:
        email_data = {
            "to": to_email,
            "subject": subject,
            "body": body,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
            "retry_count": 0
        }

        # Load existing queue
        queue_file = "email_queue.json"
        try:
            with open(queue_file, 'r') as f:
                content = f.read()
                queue = json.loads(content) if content.strip() else []
        except FileNotFoundError:
            queue = []

        # Add new email
        queue.append(email_data)

        # Save queue
        with open(queue_file, 'w') as f:
            json.dump(queue, f, indent=2)

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
            "message": "Email delivery failed"
        }


async def send_verification_email(email: str, name: str, code: str) -> dict:
    """Send verification email with fallback"""
    subject = f"{APP_NAME} - Email Verification"
    body = create_email_template(name, code, "verify")
    return await send_email_with_fallback(email, subject, body)


async def send_password_reset_email(email: str, name: str, code: str) -> dict:
    """Send password reset email with fallback"""
    subject = f"{APP_NAME} - Password Reset"
    body = create_email_template(name, code, "reset")
    return await send_email_with_fallback(email, subject, body)


def retry_queued_emails() -> dict:
    """Retry sending queued emails (synchronous for background tasks)"""
    try:
        with open("email_queue.json", 'r') as f:
            content = f.read()
            queue = json.loads(content) if content.strip() else []
    except FileNotFoundError:
        return {"processed": 0, "sent": 0, "failed": 0}

    sent = 0
    failed = 0
    remaining_queue = []

    for email_data in queue:
        try:
            success = send_email_gmail_sync(
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
            if email_data["retry_count"] < 3:  # Max 3 retries
                remaining_queue.append(email_data)
            failed += 1

    # Save remaining queue
    with open("email_queue.json", 'w') as f:
        json.dump(remaining_queue, f, indent=2)

    return {
        "processed": len(queue),
        "sent": sent,
        "failed": failed,
        "remaining": len(remaining_queue)
    }