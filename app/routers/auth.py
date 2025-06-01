from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr

from app.database import get_db, User, VerificationCode
from app.auth import (
    hash_password, verify_password, generate_code, create_access_token,
    send_verification_email, send_password_reset_email, get_current_user
)
from app.responses import success_response, error_response

router = APIRouter()


# Pydantic models
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    fullname: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class VerifyCode(BaseModel):
    email: EmailStr
    code: str


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    email: EmailStr
    code: str
    new_password: str


@router.post("/register")
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register new user"""
    # Check if user exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()

    if existing_user:
        # If user exists but not verified, allow re-registration
        if not existing_user.is_verified:
            # Update user data
            existing_user.password = hash_password(user_data.password)
            existing_user.fullname = user_data.fullname
            db.commit()

            # Delete old verification codes
            db.query(VerificationCode).filter(
                VerificationCode.email == user_data.email,
                VerificationCode.code_type == "email"
            ).delete()
            db.commit()

            # Generate new verification code
            code = generate_code()
            verification = VerificationCode(
                email=user_data.email,
                code=code,
                code_type="email",
                expires_at=datetime.utcnow() + timedelta(minutes=10)
            )
            db.add(verification)
            db.commit()

            # Send email
            try:
                await send_verification_email(user_data.email, user_data.fullname, code)
                email_sent = True
                email_error = None
            except Exception as e:
                email_sent = False
                email_error = str(e)

            return success_response(
                "Registration updated. Please verify your email",
                {
                    "user_id": existing_user.id,
                    "email": existing_user.email,
                    "email_sent": email_sent,
                    "email_error": email_error if not email_sent else None,
                    "message": "New verification code sent. Please check your email."
                },
                status_code=200
            )
        else:
            # User is already verified
            error_response("Email already registered and verified", status_code=status.HTTP_400_BAD_REQUEST)

    # Create new user
    user = User(
        email=user_data.email,
        password=hash_password(user_data.password),
        fullname=user_data.fullname
    )
    db.add(user)
    db.commit()

    # Generate verification code
    code = generate_code()
    verification = VerificationCode(
        email=user_data.email,
        code=code,
        code_type="email",
        expires_at=datetime.utcnow() + timedelta(minutes=10)
    )
    db.add(verification)
    db.commit()

    # Send email
    try:
        await send_verification_email(user_data.email, user_data.fullname, code)
        email_sent = True
        email_error = None
    except Exception as e:
        email_sent = False
        email_error = str(e)

    return success_response(
        "User registered successfully",
        {
            "user_id": user.id,
            "email": user.email,
            "email_sent": email_sent,
            "email_error": email_error if not email_sent else None,
            "message": "Please check your email for verification code" if email_sent else "Email sending failed. Use /auth/resend-code to retry."
        },
        status_code=201
    )


@router.post("/verify-email")
def verify_email(verify_data: VerifyCode, db: Session = Depends(get_db)):
    """Verify email with code"""
    # Find valid code
    code_record = db.query(VerificationCode).filter(
        VerificationCode.email == verify_data.email,
        VerificationCode.code == verify_data.code,
        VerificationCode.code_type == "email",
        VerificationCode.used == False,
        VerificationCode.expires_at > datetime.utcnow()
    ).first()

    if not code_record:
        # Check if code exists but expired
        expired_code = db.query(VerificationCode).filter(
            VerificationCode.email == verify_data.email,
            VerificationCode.code == verify_data.code,
            VerificationCode.code_type == "email",
            VerificationCode.used == False
        ).first()

        if expired_code:
            error_response("Verification code expired. Please request a new one.",
                           status_code=status.HTTP_400_BAD_REQUEST)
        else:
            error_response("Invalid verification code", status_code=status.HTTP_400_BAD_REQUEST)

    # Find user and verify
    user = db.query(User).filter(User.email == verify_data.email).first()
    if not user:
        error_response("User not found", status_code=status.HTTP_404_NOT_FOUND)

    user.is_verified = True
    code_record.used = True
    db.commit()

    # Clean up old verification codes for this user
    db.query(VerificationCode).filter(
        VerificationCode.email == verify_data.email,
        VerificationCode.code_type == "email",
        VerificationCode.used == False
    ).delete()
    db.commit()

    return success_response("Email verified successfully")


@router.post("/login")
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """Login user"""
    # Find user
    user = db.query(User).filter(User.email == login_data.email).first()

    if not user or not verify_password(login_data.password, user.password):
        error_response("Invalid email or password", status_code=status.HTTP_401_UNAUTHORIZED)

    if not user.is_verified:
        error_response(
            "Email not verified. Please verify your email or use /auth/resend-code to get a new verification code.",
            status_code=status.HTTP_403_FORBIDDEN
        )

    # Create token
    token = create_access_token({"sub": str(user.id)})

    return success_response(
        "Login successful",
        {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "fullname": user.fullname
            }
        }
    )


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return success_response(
        "User info retrieved",
        {
            "id": current_user.id,
            "email": current_user.email,
            "fullname": current_user.fullname,
            "is_verified": current_user.is_verified,
            "created_at": current_user.created_at.isoformat()
        }
    )


@router.post("/forgot-password")
async def forgot_password(forgot_data: ForgotPassword, db: Session = Depends(get_db)):
    """Request password reset"""
    user = db.query(User).filter(User.email == forgot_data.email).first()
    if not user:
        error_response("Email not found", status_code=status.HTTP_404_NOT_FOUND)

    # Delete old password reset codes
    db.query(VerificationCode).filter(
        VerificationCode.email == forgot_data.email,
        VerificationCode.code_type == "password_reset",
        VerificationCode.used == False
    ).delete()
    db.commit()

    # Generate reset code
    code = generate_code()
    verification = VerificationCode(
        email=forgot_data.email,
        code=code,
        code_type="password_reset",
        expires_at=datetime.utcnow() + timedelta(minutes=15)
    )
    db.add(verification)
    db.commit()

    # Send email
    try:
        await send_password_reset_email(forgot_data.email, user.fullname, code)
        return success_response("Password reset code sent to your email")
    except Exception as e:
        error_response(f"Failed to send email: {str(e)}", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@router.post("/reset-password")
def reset_password(reset_data: ResetPassword, db: Session = Depends(get_db)):
    """Reset password with code"""
    # Find valid code
    code_record = db.query(VerificationCode).filter(
        VerificationCode.email == reset_data.email,
        VerificationCode.code == reset_data.code,
        VerificationCode.code_type == "password_reset",
        VerificationCode.used == False,
        VerificationCode.expires_at > datetime.utcnow()
    ).first()

    if not code_record:
        error_response("Invalid or expired reset code", status_code=status.HTTP_400_BAD_REQUEST)

    # Find user and update password
    user = db.query(User).filter(User.email == reset_data.email).first()
    if not user:
        error_response("User not found", status_code=status.HTTP_404_NOT_FOUND)

    user.password = hash_password(reset_data.new_password)
    code_record.used = True
    db.commit()

    # Clean up old codes
    db.query(VerificationCode).filter(
        VerificationCode.email == reset_data.email,
        VerificationCode.code_type == "password_reset",
        VerificationCode.used == False
    ).delete()
    db.commit()

    return success_response("Password reset successfully")


@router.post("/resend-code")
async def resend_code(email_data: ForgotPassword, db: Session = Depends(get_db)):
    """Resend verification code"""
    user = db.query(User).filter(User.email == email_data.email).first()
    if not user:
        error_response("Email not found", status_code=status.HTTP_404_NOT_FOUND)

    # Determine code type
    code_type = "email" if not user.is_verified else "password_reset"

    # Check if user already verified and requesting email verification
    if user.is_verified and code_type == "email":
        error_response("Email already verified", status_code=status.HTTP_400_BAD_REQUEST)

    # Delete old codes of the same type
    db.query(VerificationCode).filter(
        VerificationCode.email == email_data.email,
        VerificationCode.code_type == code_type,
        VerificationCode.used == False
    ).delete()
    db.commit()

    # Generate new code
    code = generate_code()
    verification = VerificationCode(
        email=email_data.email,
        code=code,
        code_type=code_type,
        expires_at=datetime.utcnow() + timedelta(minutes=10)
    )
    db.add(verification)
    db.commit()

    # Send email
    try:
        if code_type == "email":
            await send_verification_email(email_data.email, user.fullname, code)
            message = "Email verification code sent"
        else:
            await send_password_reset_email(email_data.email, user.fullname, code)
            message = "Password reset code sent"

        return success_response(message, {
            "email": email_data.email,
            "code_type": code_type,
            "expires_in_minutes": 10
        })
    except Exception as e:
        error_response(f"Failed to send email: {str(e)}", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@router.get("/check-verification-status/{email}")
def check_verification_status(email: EmailStr, db: Session = Depends(get_db)):
    """Check if email is registered and verified"""
    user = db.query(User).filter(User.email == email).first()

    if not user:
        return success_response("Email not registered", {
            "email": email,
            "registered": False,
            "verified": False
        })

    return success_response("Email status retrieved", {
        "email": email,
        "registered": True,
        "verified": user.is_verified,
        "can_login": user.is_verified,
        "needs_verification": not user.is_verified
    })