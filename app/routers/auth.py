from fastapi import APIRouter, Depends, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr

from app.config import settings
from app.database import get_db, User, VerificationCode
from app.auth import (
    hash_password, verify_password, generate_code, create_access_token,
    send_verification_email, send_password_reset_email, get_current_user,
    verify_code_with_fallback, cleanup_temp_codes
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
def register(user_data: UserRegister, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Register new user with improved email handling"""
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

            # Send email with fallback
            try:
                email_result = send_verification_email(user_data.email, user_data.fullname, code, background_tasks)

                return success_response(
                    "Registration updated successfully",
                    {
                        "user_id": existing_user.id,
                        "email": existing_user.email,
                        "email_sent": email_result["email_sent"],
                        "fallback_used": email_result["fallback_used"],
                        "message": email_result["message"]
                    },
                    status_code=200
                )
            except Exception as e:
                return success_response(
                    "Registration updated - email service unavailable",
                    {
                        "user_id": existing_user.id,
                        "email": existing_user.email,
                        "email_sent": False,
                        "message": f"Registration successful but email failed: {str(e)}. Contact support for manual verification."
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

    # Send email with fallback
    try:
        email_result = send_verification_email(user_data.email, user_data.fullname, code, background_tasks)

        return success_response(
            "User registered successfully",
            {
                "user_id": user.id,
                "email": user.email,
                "email_sent": email_result["email_sent"],
                "fallback_used": email_result["fallback_used"],
                "message": email_result["message"]
            },
            status_code=201
        )
    except Exception as e:
        return success_response(
            "User registered - email service unavailable",
            {
                "user_id": user.id,
                "email": user.email,
                "email_sent": False,
                "message": f"Registration successful but email failed: {str(e)}. Contact support for manual verification."
            },
            status_code=201
        )


@router.post("/verify-email")
def verify_email(verify_data: VerifyCode, db: Session = Depends(get_db)):
    """Verify email with code (supports fallback codes)"""
    # Use enhanced verification that checks both DB and temp storage
    if not verify_code_with_fallback(verify_data.email, verify_data.code, "email", db):
        error_response("Invalid or expired verification code", status_code=status.HTTP_400_BAD_REQUEST)

    # Find user and verify
    user = db.query(User).filter(User.email == verify_data.email).first()
    if not user:
        error_response("User not found", status_code=status.HTTP_404_NOT_FOUND)

    user.is_verified = True
    db.commit()

    # Clean up old verification codes for this user
    db.query(VerificationCode).filter(
        VerificationCode.email == verify_data.email,
        VerificationCode.code_type == "email",
        VerificationCode.used == False
    ).delete()
    db.commit()

    return success_response("Email verified successfully", {
        "user_id": user.id,
        "email": user.email,
        "verified": True
    })


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
def forgot_password(forgot_data: ForgotPassword, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
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

    # Send email with fallback
    try:
        email_result = send_password_reset_email(forgot_data.email, user.fullname, code, background_tasks)

        return success_response(
            "Password reset requested",
            {
                "email": forgot_data.email,
                "email_sent": email_result["email_sent"],
                "fallback_used": email_result["fallback_used"],
                "message": email_result["message"]
            }
        )
    except Exception as e:
        return success_response(
            "Password reset requested - email service unavailable",
            {
                "email": forgot_data.email,
                "email_sent": False,
                "message": f"Reset code generated but email failed: {str(e)}. Contact support for assistance."
            }
        )


@router.post("/reset-password")
def reset_password(reset_data: ResetPassword, db: Session = Depends(get_db)):
    """Reset password with code (supports fallback codes)"""
    # Use enhanced verification that checks both DB and temp storage
    if not verify_code_with_fallback(reset_data.email, reset_data.code, "password_reset", db):
        error_response("Invalid or expired reset code", status_code=status.HTTP_400_BAD_REQUEST)

    # Find user and update password
    user = db.query(User).filter(User.email == reset_data.email).first()
    if not user:
        error_response("User not found", status_code=status.HTTP_404_NOT_FOUND)

    user.password = hash_password(reset_data.new_password)
    db.commit()

    # Clean up old codes
    db.query(VerificationCode).filter(
        VerificationCode.email == reset_data.email,
        VerificationCode.code_type == "password_reset",
        VerificationCode.used == False
    ).delete()
    db.commit()

    return success_response("Password reset successfully", {
        "email": reset_data.email,
        "reset_completed": True
    })


@router.post("/resend-code")
def resend_code(email_data: ForgotPassword, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
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

    # Send email with fallback
    try:
        if code_type == "email":
            email_result = send_verification_email(email_data.email, user.fullname, code, background_tasks)
            message = "Email verification code resent"
        else:
            email_result = send_password_reset_email(email_data.email, user.fullname, code, background_tasks)
            message = "Password reset code resent"

        return success_response(message, {
            "email": email_data.email,
            "code_type": code_type,
            "email_sent": email_result["email_sent"],
            "fallback_used": email_result["fallback_used"],
            "message": email_result["message"],
            "expires_in_minutes": 10
        })
    except Exception as e:
        return success_response(
            f"Code generated - email service unavailable",
            {
                "email": email_data.email,
                "code_type": code_type,
                "email_sent": False,
                "message": f"Code generated but email failed: {str(e)}. Contact support for assistance.",
                "expires_in_minutes": 10
            }
        )


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


# Admin/Debug endpoints for manual verification (development only)
@router.post("/manual-verify")
def manual_verify_email(verify_data: VerifyCode, db: Session = Depends(get_db)):
    """Manual email verification (when email service is unavailable)"""
    if not settings.DEBUG:
        error_response("Endpoint only available in debug mode", status_code=status.HTTP_403_FORBIDDEN)

    user = db.query(User).filter(User.email == verify_data.email).first()
    if not user:
        error_response("User not found", status_code=status.HTTP_404_NOT_FOUND)

    if user.is_verified:
        error_response("Email already verified", status_code=status.HTTP_400_BAD_REQUEST)

    # Manually verify the user (for development/testing)
    user.is_verified = True
    db.commit()

    return success_response("Email manually verified", {
        "user_id": user.id,
        "email": user.email,
        "verified": True,
        "note": "Manual verification - only available in debug mode"
    })


@router.post("/cleanup-temp-codes")
def cleanup_temporary_codes():
    """Clean up expired temporary codes"""
    if not settings.DEBUG:
        error_response("Endpoint only available in debug mode", status_code=status.HTTP_403_FORBIDDEN)

    cleanup_temp_codes()
    return success_response("Temporary codes cleaned up")