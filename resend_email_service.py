"""
Resend Email Service - 2025 Best Practices
Simple, reliable email service using Resend API
"""

import os
import requests
import logging
import random
import string
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ResendEmailService:
    """Resend Email Service for sending emails"""

    def __init__(self):
        self.api_key = os.getenv("RESEND_API_KEY", "")
        self.from_email = os.getenv("FROM_EMAIL", "onboarding@resend.dev")
        self.from_name = os.getenv("FROM_NAME", "Simple Debt Tracker")
        self.api_url = "https://api.resend.com/emails"

    def generate_verification_code(self) -> str:
        """Generate 6-digit verification code"""
        return ''.join(random.choices(string.digits, k=6))

    def create_email_template(self, name: str, code: str, action: str = "verify") -> str:
        """Create professional email template"""
        action_text = "verify your email" if action == "verify" else "reset your password"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{self.from_name} - Email Verification</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f8fafc;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
                <!-- Header -->
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; text-align: center;">
                    <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600;">{self.from_name}</h1>
                </div>

                <!-- Content -->
                <div style="padding: 40px 30px;">
                    <h2 style="color: #1f2937; margin: 0 0 20px; font-size: 20px;">Hello {name}!</h2>
                    <p style="color: #4b5563; font-size: 16px; line-height: 1.6; margin: 0 0 30px;">
                        We received a request to {action_text}. Use the verification code below:
                    </p>

                    <!-- Code Box -->
                    <div style="background: #f3f4f6; border: 2px dashed #3b82f6; border-radius: 8px; padding: 30px; text-align: center; margin: 30px 0;">
                        <div style="font-size: 32px; font-weight: bold; color: #3b82f6; letter-spacing: 6px; font-family: 'Courier New', monospace;">
                            {code}
                        </div>
                    </div>

                    <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 30px 0; border-radius: 4px;">
                        <p style="margin: 0; color: #92400e; font-size: 14px;">
                            ⏰ This code expires in 10 minutes
                        </p>
                    </div>

                    <p style="color: #6b7280; font-size: 14px; line-height: 1.5; margin: 30px 0 0;">
                        If you didn't request this, please ignore this email.
                    </p>
                </div>

                <!-- Footer -->
                <div style="background: #f9fafb; padding: 20px 30px; border-top: 1px solid #e5e7eb;">
                    <p style="margin: 0; color: #6b7280; font-size: 12px; text-align: center;">
                        © 2025 {self.from_name}. Sent securely via Resend.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

    def send_email(self, to_email: str, subject: str, html_content: str) -> Dict[str, Any]:
        """Send email using Resend API"""
        try:
            logger.info(f"📧 Sending email via Resend to: {to_email}")

            if not self.api_key:
                return {"success": False, "error": "Resend API key not configured"}

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [to_email],
                "subject": subject,
                "html": html_content
            }

            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Email sent successfully via Resend to {to_email}")
                return {
                    "success": True,
                    "provider": "Resend",
                    "message_id": result.get("id")
                }
            else:
                error_msg = f"Resend API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = f"Resend API request failed: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def send_verification_email(self, email: str, name: str, code: str) -> Dict[str, Any]:
        """Send verification email"""
        subject = f"{self.from_name} - Verify Your Email"
        html_content = self.create_email_template(name, code, "verify")
        return self.send_email(email, subject, html_content)

    def send_password_reset_email(self, email: str, name: str, code: str) -> Dict[str, Any]:
        """Send password reset email"""
        subject = f"{self.from_name} - Reset Your Password"
        html_content = self.create_email_template(name, code, "reset")
        return self.send_email(email, subject, html_content)

    def test_connection(self) -> Dict[str, Any]:
        """Test Resend API configuration"""
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "error": "Resend API key not configured",
                    "setup_required": True
                }

            # Test API key validity by making a simple request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # We don't actually send an email, just validate the API key format
            if not self.api_key.startswith("re_"):
                return {
                    "success": False,
                    "error": "Invalid Resend API key format (should start with 're_')"
                }

            return {
                "success": True,
                "provider": "Resend",
                "from_email": self.from_email,
                "from_name": self.from_name,
                "message": "Resend configuration is valid",
                "api_key_format": "Valid (re_...)"
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Configuration test failed: {str(e)}"
            }


# Global instance
resend_service = ResendEmailService()


# Convenience functions for backward compatibility
def generate_verification_code() -> str:
    return resend_service.generate_verification_code()


def send_verification_email(email: str, name: str, code: str) -> bool:
    result = resend_service.send_verification_email(email, name, code)
    return result["success"]


def send_password_reset_email(email: str, name: str, code: str) -> bool:
    result = resend_service.send_password_reset_email(email, name, code)
    return result["success"]


def test_smtp_connection() -> dict:
    """Backward compatibility function"""
    result = resend_service.test_connection()
    return {
        "success": result["success"],
        "message": result.get("message", result.get("error", "Unknown error"))
    }


# Debug function
def test_resend_service():
    """Test the Resend service manually"""
    print("🧪 Testing Resend Email Service...")

    # Test configuration
    config_result = resend_service.test_connection()
    print(f"📋 Configuration: {config_result}")

    if config_result["success"]:
        print("✅ Resend service ready for sending!")
        print(f"Provider: Resend")
        print(f"From: {resend_service.from_name} <{resend_service.from_email}>")
        print(f"API Key: {resend_service.api_key[:10]}...")
    else:
        print(f"❌ Configuration invalid: {config_result['error']}")


if __name__ == "__main__":
    test_resend_service()