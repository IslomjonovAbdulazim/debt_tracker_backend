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
    if db.query(User).filter(User.email == user_data.email).first():
        error_response("Email already registered", status_code=status.HTTP_400_BAD_REQUEST)

    # Create user
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
    except:
        email_sent = False

    return success_response(
        "User registered successfully",
        {
            "user_id": user.id,
            "email": user.email,
            "email_sent": email_sent,
            "message": "Please check your email for verification code"
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
        error_response("Invalid or expired verification code", status_code=status.HTTP_400_BAD_REQUEST)

    # Find user and verify
    user = db.query(User).filter(User.email == verify_data.email).first()
    if not user:
        error_response("User not found", status_code=status.HTTP_404_NOT_FOUND)

    user.is_verified = True
    code_record.used = True
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
        error_response("Please verify your email first", status_code=status.HTTP_403_FORBIDDEN)

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
    except:
        error_response("Failed to send email", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


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

    return success_response("Password reset successfully")


@router.post("/resend-code")
async def resend_code(email_data: ForgotPassword, db: Session = Depends(get_db)):
    """Resend verification code"""
    user = db.query(User).filter(User.email == email_data.email).first()
    if not user:
        error_response("Email not found", status_code=status.HTTP_404_NOT_FOUND)

    # Generate new code
    code = generate_code()
    verification = VerificationCode(
        email=email_data.email,
        code=code,
        code_type="email" if not user.is_verified else "password_reset",
        expires_at=datetime.utcnow() + timedelta(minutes=10)
    )
    db.add(verification)
    db.commit()

    # Send email
    try:
        if not user.is_verified:
            await send_verification_email(email_data.email, user.fullname, code)
        else:
            await send_password_reset_email(email_data.email, user.fullname, code)
        return success_response("Verification code sent")
    except:
        error_response("Failed to send email", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)