import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD", "")


def test_gmail_connection():
    """Test Gmail SMTP connection"""
    print(f"Testing Gmail connection...")
    print(f"Email: {GMAIL_USER}")
    print(f"Password: {'*' * len(GMAIL_PASSWORD) if GMAIL_PASSWORD else 'NOT SET'}")

    if not GMAIL_USER or not GMAIL_PASSWORD:
        print("❌ Gmail credentials not configured")
        return False

    try:
        # Test connection
        print("🔄 Connecting to Gmail SMTP...")
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            print("🔄 Starting TLS...")
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            print("✅ Gmail authentication successful!")

            # Send test email
            msg = MIMEMultipart()
            msg['Subject'] = "Test Email from Debt Tracker"
            msg['From'] = GMAIL_USER
            msg['To'] = GMAIL_USER  # Send to yourself

            body = "This is a test email to verify Gmail integration works!"
            msg.attach(MIMEText(body, 'plain'))

            server.send_message(msg)
            print(f"✅ Test email sent successfully to {GMAIL_USER}")
            return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Gmail authentication failed: {e}")
        print("❌ Possible issues:")
        print("   1. Wrong app password")
        print("   2. 2FA not enabled")
        print("   3. App passwords not generated")
        print("   4. Using regular password instead of app password")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    test_gmail_connection()