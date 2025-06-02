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

# Email configuration
EMAIL_SERVICE = os.getenv("EMAIL_SERVICE", "test")  # Options: gmail, test
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD", "")
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
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #333; text-align: center;">Welcome to {APP_NAME}!</h2>
        <p>Hi {name},</p>
        <p>Your verification code to {action_text} is:</p>
        <div style="font-size: 32px; font-weight: bold; color: #007bff; text-align: center; 
                    padding: 20px; background: #f8f9fa; border-radius: 8px; margin: 20px 0;
                    border: 2px solid #007bff;">
            {code}
        </div>
        <p style="text-align: center;"><strong>This code expires in 10 minutes.</strong></p>
        <p style="color: #666;">If you didn't request this, please ignore this email.</p>
        <hr style="margin: 20px 0;">
        <p style="color: #666; font-size: 12px; text-align: center;">© 2025 {APP_NAME}</p>
    </div>
    """


def send_email_gmail(to_email: str, subject: str, body: str) -> bool:
    """Send email using Gmail SMTP"""
    try:
        if not GMAIL_USER or not GMAIL_PASSWORD:
            print(f"❌ Gmail credentials not configured")
            return False

        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = GMAIL_USER
        msg['To'] = to_email

        # Add HTML content
        html_part = MIMEText(body, 'html', 'utf-8')
        msg.attach(html_part)

        # Send email
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.send_message(msg)

        print(f"✅ Email sent successfully to {to_email}")
        return True

    except smtplib.SMTPAuthenticationError:
        print(f"❌ Gmail authentication failed. Check your app password.")
        return False
    except smtplib.SMTPException as e:
        print(f"❌ Gmail SMTP error: {e}")
        return False
    except Exception as e:
        print(f"❌ Gmail error: {e}")
        return False


def send_email_test(to_email: str, subject: str, body: str) -> bool:
    """Test email - just print to console"""
    print(f"\n📧 TEST EMAIL")
    print(f"📧 TO: {to_email}")
    print(f"📧 SUBJECT: {subject}")
    print(f"📧 CODE: {extract_code_from_body(body)}")
    print(f"📧 Full body logged to console\n")
    return True


def extract_code_from_body(body: str) -> str:
    """Extract verification code from email body for testing"""
    import re
    # Look for 6 digits in the email body
    match = re.search(r'\b\d{6}\b', body)
    return match.group() if match else "CODE_NOT_FOUND"


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send email using configured service"""
    if EMAIL_SERVICE == "gmail":
        return send_email_gmail(to_email, subject, body)
    else:
        # Default to test mode
        return send_email_test(to_email, subject, body)


def send_verification_email(email: str, name: str, code: str) -> dict:
    """Send verification email"""
    subject = f"{APP_NAME} - Email Verification"
    body = create_email_template(name, code, "verify")

    success = send_email(email, subject, body)

    result = {
        "email_sent": success,
        "message": "Verification email sent" if success else "Email service unavailable"
    }

    # In test mode or if email failed, include the code in response
    if EMAIL_SERVICE == "test" or not success:
        result["code"] = code

    return result


def send_password_reset_email(email: str, name: str, code: str) -> dict:
    """Send password reset email"""
    subject = f"{APP_NAME} - Password Reset"
    body = create_email_template(name, code, "reset")

    success = send_email(email, subject, body)

    result = {
        "email_sent": success,
        "message": "Reset email sent" if success else "Email service unavailable"
    }

    # In test mode or if email failed, include the code in response
    if EMAIL_SERVICE == "test" or not success:
        result["code"] = code

    return result