import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from dotenv import load_dotenv
import random
import string

load_dotenv()

# Configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("GMAIL_USER", "")
SMTP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Simple Debt Tracker")

logger = logging.getLogger(__name__)


def generate_verification_code() -> str:
    """Generate 6-digit verification code"""
    return ''.join(random.choices(string.digits, k=6))


def create_verification_email_template(name: str, code: str, action: str = "verify") -> str:
    """Create simple email template"""
    action_text = "verify your email" if action == "verify" else "reset your password"

    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">Hello {name}!</h2>

            <p>We received a request to {action_text}.</p>

            <div style="background: #f0f0f0; padding: 20px; text-align: center; margin: 20px 0;">
                <h1 style="color: #007bff; letter-spacing: 5px; margin: 0;">{code}</h1>
            </div>

            <p><strong>This code expires in 10 minutes.</strong></p>

            <p style="color: #666; font-size: 14px;">
                If you didn't request this, please ignore this email.
            </p>

            <hr>
            <p style="color: #999; font-size: 12px;">
                This is an automated message from Simple Debt Tracker.
            </p>
        </div>
    </body>
    </html>
    """


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send email via SMTP"""
    try:
        # Validate configuration
        if not SMTP_USER or not SMTP_PASSWORD:
            logger.error("SMTP credentials not configured")
            return False

        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = formataddr((FROM_NAME, SMTP_USER))
        msg['To'] = to_email

        # Add HTML content
        html_part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(html_part)

        # Connect and send
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"Email sent successfully to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_verification_email(email: str, name: str, code: str) -> bool:
    """Send verification email"""
    subject = "Simple Debt Tracker - Verify Your Email"
    html_body = create_verification_email_template(name, code, "verify")
    return send_email(email, subject, html_body)


def send_password_reset_email(email: str, name: str, code: str) -> bool:
    """Send password reset email"""
    subject = "Simple Debt Tracker - Reset Your Password"
    html_body = create_verification_email_template(name, code, "reset")
    return send_email(email, subject, html_body)


def test_smtp_connection() -> dict:
    """Test SMTP connection"""
    try:
        if not SMTP_USER or not SMTP_PASSWORD:
            return {
                "success": False,
                "message": "SMTP credentials not configured"
            }

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)

        return {
            "success": True,
            "message": "SMTP connection successful"
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"SMTP connection failed: {str(e)}"
        }