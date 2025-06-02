from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# Email configuration - choose ONE method
EMAIL_SERVICE = os.getenv("EMAIL_SERVICE", "gmail")  # Options: gmail, sendgrid, mailgun

# Gmail settings (easiest to start with)
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD", "")  # Use app password

# SendGrid settings (recommended for production)
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")

# Mailgun settings (also good for production)
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY", "")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN", "")

APP_NAME = os.getenv("APP_NAME", "Simple Debt Tracker")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
# EMAIL FUNCTIONS
# ==================

def generate_code() -> str:
    """Generate 6-digit verification code"""
    return ''.join(random.choices(string.digits, k=6))


def create_email_template(name: str, code: str, action: str = "verify") -> str:
    """Create simple email template"""
    action_text = "verify your email" if action == "verify" else "reset your password"

    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #333;">Welcome to {APP_NAME}!</h2>
        <p>Hi {name},</p>
        <p>Your verification code to {action_text} is:</p>
        <div style="font-size: 32px; font-weight: bold; color: #007bff; text-align: center; 
                    padding: 20px; background: #f8f9fa; border-radius: 8px; margin: 20px 0;">
            {code}
        </div>
        <p><strong>This code expires in 10 minutes.</strong></p>
        <p>If you didn't request this, please ignore this email.</p>
        <hr>
        <p style="color: #666; font-size: 12px;">© 2025 {APP_NAME}</p>
    </div>
    """


def send_email_gmail(to_email: str, subject: str, body: str) -> bool:
    """Send email using Gmail SMTP"""
    try:
        if not GMAIL_USER or not GMAIL_PASSWORD:
            print(f"Gmail not configured. Would send: {subject}")
            return False

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = GMAIL_USER
        msg['To'] = to_email

        html_part = MIMEText(body, 'html')
        msg.attach(html_part)

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.send_message(msg)

        print(f"✅ Email sent successfully to {to_email}")
        return True

    except Exception as e:
        print(f"❌ Gmail error: {e}")
        return False


def send_email_sendgrid(to_email: str, subject: str, body: str) -> bool:
    """Send email using SendGrid API"""
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail

        if not SENDGRID_API_KEY:
            print("SendGrid not configured")
            return False

        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
        message = Mail(
            from_email=f"noreply@yourapp.com",
            to_emails=to_email,
            subject=subject,
            html_content=body
        )
        response = sg.send(message)

        print(f"✅ SendGrid email sent to {to_email}")
        return response.status_code == 202

    except Exception as e:
        print(f"❌ SendGrid error: {e}")
        return False


def send_email_mailgun(to_email: str, subject: str, body: str) -> bool:
    """Send email using Mailgun API"""
    try:
        import requests

        if not MAILGUN_API_KEY or not MAILGUN_DOMAIN:
            print("Mailgun not configured")
            return False

        response = requests.post(
            f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
            auth=("api", MAILGUN_API_KEY),
            data={
                "from": f"{APP_NAME} <noreply@{MAILGUN_DOMAIN}>",
                "to": to_email,
                "subject": subject,
                "html": body
            }
        )

        print(f"✅ Mailgun email sent to {to_email}")
        return response.status_code == 200

    except Exception as e:
        print(f"❌ Mailgun error: {e}")
        return False


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send email using configured service"""

    if EMAIL_SERVICE == "sendgrid":
        return send_email_sendgrid(to_email, subject, body)
    elif EMAIL_SERVICE == "mailgun":
        return send_email_mailgun(to_email, subject, body)
    elif EMAIL_SERVICE == "gmail":
        return send_email_gmail(to_email, subject, body)
    else:
        # For testing - just print the email
        print(f"\n📧 EMAIL TO: {to_email}")
        print(f"📧 SUBJECT: {subject}")
        print(f"📧 BODY: {body}\n")
        return True  # Return True for testing


def send_verification_email(email: str, name: str, code: str) -> dict:
    """Send verification email"""
    subject = f"{APP_NAME} - Email Verification"
    body = create_email_template(name, code, "verify")

    success = send_email(email, subject, body)

    return {
        "email_sent": success,
        "message": "Verification email sent" if success else "Email service unavailable",
        "code": code if not success else None  # Show code if email failed
    }


def send_password_reset_email(email: str, name: str, code: str) -> dict:
    """Send password reset email"""
    subject = f"{APP_NAME} - Password Reset"
    body = create_email_template(name, code, "reset")

    success = send_email(email, subject, body)

    return {
        "email_sent": success,
        "message": "Reset email sent" if success else "Email service unavailable",
        "code": code if not success else None  # Show code if email failed
    }