import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import aiofiles
import json
from datetime import datetime
from typing import Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.gmail_user = os.getenv("GMAIL_USER", "")
        self.gmail_password = os.getenv("GMAIL_PASSWORD", "")
        self.app_name = os.getenv("APP_NAME", "Simple Debt Tracker")
        self.fallback_file = "email_queue.json"

    async def send_email_async(self, to_email: str, subject: str, body: str, timeout: int = 10) -> dict:
        """Send email with timeout and fallback"""
        try:
            # Try to send email with timeout
            result = await asyncio.wait_for(
                self._send_gmail_async(to_email, subject, body),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Email timeout for {to_email}")
            return await self._fallback_save_email(to_email, subject, body, "timeout")
        except Exception as e:
            logger.error(f"Email error for {to_email}: {e}")
            return await self._fallback_save_email(to_email, subject, body, str(e))

    async def _send_gmail_async(self, to_email: str, subject: str, body: str) -> dict:
        """Send email via Gmail SMTP (async wrapper)"""

        def _send_sync():
            if not self.gmail_user or not self.gmail_password:
                raise Exception("Gmail credentials not configured")

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.gmail_user
            msg['To'] = to_email
            msg.attach(MIMEText(body, 'html', 'utf-8'))

            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(self.gmail_user, self.gmail_password)
                server.send_message(msg)

        # Run sync email in thread pool
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _send_sync)

        return {
            "success": True,
            "method": "email",
            "message": "Email sent successfully"
        }

    async def _fallback_save_email(self, to_email: str, subject: str, body: str, error: str) -> dict:
        """Save email to file when sending fails"""
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
            try:
                async with aiofiles.open(self.fallback_file, 'r') as f:
                    content = await f.read()
                    queue = json.loads(content) if content.strip() else []
            except FileNotFoundError:
                queue = []

            # Add new email
            queue.append(email_data)

            # Save queue
            async with aiofiles.open(self.fallback_file, 'w') as f:
                await f.write(json.dumps(queue, indent=2))

            logger.info(f"Email saved to queue for {to_email}")
            return {
                "success": True,
                "method": "queue",
                "message": "Email queued for later delivery"
            }

        except Exception as e:
            logger.error(f"Failed to save email to queue: {e}")
            return {
                "success": False,
                "method": "failed",
                "message": "Email delivery failed completely"
            }

    def create_simple_template(self, name: str, code: str, action: str = "verify") -> str:
        """Create minimal email template"""
        action_text = "verify your email" if action == "verify" else "reset your password"

        return f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; max-width: 500px;">
            <h2>{self.app_name}</h2>
            <p>Hi {name},</p>
            <p>Your code to {action_text}:</p>
            <h1 style="color: #007bff; text-align: center; padding: 15px; background: #f8f9fa; border-radius: 5px;">
                {code}
            </h1>
            <p><strong>Expires in 10 minutes</strong></p>
            <p style="color: #666; font-size: 12px;">If you didn't request this, ignore this email.</p>
        </div>
        """

    async def send_verification_email(self, email: str, name: str, code: str) -> dict:
        """Send verification email"""
        subject = f"{self.app_name} - Verify Email"
        body = self.create_simple_template(name, code, "verify")
        return await self.send_email_async(email, subject, body)

    async def send_password_reset_email(self, email: str, name: str, code: str) -> dict:
        """Send password reset email"""
        subject = f"{self.app_name} - Reset Password"
        body = self.create_simple_template(name, code, "reset")
        return await self.send_email_async(email, subject, body)

    async def retry_queued_emails(self) -> dict:
        """Retry sending queued emails (for background task)"""
        try:
            async with aiofiles.open(self.fallback_file, 'r') as f:
                content = await f.read()
                queue = json.loads(content) if content.strip() else []
        except FileNotFoundError:
            return {"processed": 0, "sent": 0, "failed": 0}

        sent = 0
        failed = 0
        remaining_queue = []

        for email_data in queue:
            try:
                result = await self._send_gmail_async(
                    email_data["to"],
                    email_data["subject"],
                    email_data["body"]
                )
                if result["success"]:
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
        async with aiofiles.open(self.fallback_file, 'w') as f:
            await f.write(json.dumps(remaining_queue, indent=2))

        return {
            "processed": len(queue),
            "sent": sent,
            "failed": failed,
            "remaining": len(remaining_queue)
        }


# Global email service instance
email_service = EmailService()