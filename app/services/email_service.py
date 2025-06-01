# app/services/email_service.py
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from typing import List

# Email configuration with your actual Gmail settings
conf = ConnectionConfig(
    MAIL_USERNAME="islomjonov.abdulazim.27@gmail.com",  # Your email
    MAIL_PASSWORD="pkaluadtivormjjl",  # App password WITHOUT spaces
    MAIL_FROM="islomjonov.abdulazim.27@gmail.com",  # Your email
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=False,  # Changed to False to bypass SSL verification
    MAIL_FROM_NAME="Debt Tracker App"
)

# FastMail instance
fastmail = FastMail(conf)


# Email templates
def get_verification_email_template(user_name: str, verification_code: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .code {{ background: #667eea; color: white; padding: 15px; text-align: center; font-size: 24px; font-weight: bold; border-radius: 5px; margin: 20px 0; letter-spacing: 3px; }}
            .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>💰 Debt Tracker</h1>
                <h2>Email Verification</h2>
            </div>
            <div class="content">
                <h3>Hello {user_name}!</h3>
                <p>Thank you for registering with Debt Tracker. To complete your email verification, please use the code below:</p>
                <div class="code">{verification_code}</div>
                <p>This code will expire in 10 minutes for security reasons.</p>
                <p>If you didn't request this verification, please ignore this email.</p>
            </div>
            <div class="footer">
                <p>© 2025 Debt Tracker API. This is an automated message.</p>
            </div>
        </div>
    </body>
    </html>
    """


def get_password_reset_email_template(user_name: str, reset_code: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #dc3545 0%, #e83e8c 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .code {{ background: #dc3545; color: white; padding: 15px; text-align: center; font-size: 24px; font-weight: bold; border-radius: 5px; margin: 20px 0; letter-spacing: 3px; }}
            .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Password Reset</h1>
                <h2>Debt Tracker</h2>
            </div>
            <div class="content">
                <h3>Hello {user_name}!</h3>
                <p>You requested a password reset for your Debt Tracker account. Use the code below to reset your password:</p>
                <div class="code">{reset_code}</div>
                <p>This code will expire in 15 minutes for security reasons.</p>
                <p><strong>If you didn't request this reset, please ignore this email and your password will remain unchanged.</strong></p>
            </div>
            <div class="footer">
                <p>© 2025 Debt Tracker API. This is an automated message.</p>
            </div>
        </div>
    </body>
    </html>
    """


# Email sending functions
async def send_verification_email(email: str, user_name: str, verification_code: str):
    """Send email verification code"""
    html_content = get_verification_email_template(user_name, verification_code)

    message = MessageSchema(
        subject="✉️ Verify Your Email - Debt Tracker",
        recipients=[email],
        body=html_content,
        subtype=MessageType.html
    )

    try:
        await fastmail.send_message(message)
        return {"status": "success", "message": "Verification email sent"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to send email: {str(e)}"}


async def send_password_reset_email(email: str, user_name: str, reset_code: str):
    """Send password reset code"""
    html_content = get_password_reset_email_template(user_name, reset_code)

    message = MessageSchema(
        subject="🔑 Password Reset Code - Debt Tracker",
        recipients=[email],
        body=html_content,
        subtype=MessageType.html
    )

    try:
        await fastmail.send_message(message)
        return {"status": "success", "message": "Password reset email sent"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to send email: {str(e)}"}