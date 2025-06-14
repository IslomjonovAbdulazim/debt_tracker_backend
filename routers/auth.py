from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from database import get_db, User, VerificationCode
from models import UserRegister, UserLogin, VerifyCode, ForgotPassword, ResetPassword
from auth_utils import hash_password, verify_password, create_access_token, verify_token
from resend_email_service import (
    resend_service,
    generate_verification_code,
    send_verification_email,
    send_password_reset_email,
    test_smtp_connection
)

router = APIRouter()
security = HTTPBearer()


# ==================
# DEPENDENCY: GET CURRENT USER
# ==================

def get_current_user(token: str = Depends(security), db: Session = Depends(get_db)):
    """Get current authenticated user"""
    try:
        token_data = verify_token(token.credentials)
        user = db.query(User).filter(User.id == token_data["user_id"]).first()

        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        if not user.is_verified:
            raise HTTPException(status_code=403, detail="Email not verified")

        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


# ==================
# AUTH ROUTES
# ==================

@router.post("/register")
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user with Resend email service"""

    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        if existing_user.is_verified:
            raise HTTPException(status_code=400, detail="Email already registered")
        else:
            # Delete unverified user and re-register
            db.delete(existing_user)
            db.commit()

    # Create new user
    user = User(
        email=user_data.email,
        password=hash_password(user_data.password),
        fullname=user_data.fullname,
        is_verified=False
    )
    db.add(user)
    db.commit()

    # Delete old verification codes for this email
    db.query(VerificationCode).filter(VerificationCode.email == user_data.email).delete()
    db.commit()

    # Generate verification code
    code = generate_verification_code()
    verification = VerificationCode(
        email=user_data.email,
        code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
        used=False
    )
    db.add(verification)
    db.commit()

    # Send verification email via Resend
    email_result = resend_service.send_verification_email(user_data.email, user_data.fullname, code)

    return {
        "success": True,
        "message": "User registered successfully. Please check your email for verification code.",
        "data": {
            "user_id": user.id,
            "email": user.email,
            "email_sent": email_result["success"],
            "email_provider": email_result.get("provider", "Resend"),
            "email_details": email_result
        }
    }


@router.post("/verify-email")
def verify_email(verify_data: VerifyCode, db: Session = Depends(get_db)):
    """Verify email with code"""

    # Find valid verification code
    code_record = db.query(VerificationCode).filter(
        VerificationCode.email == verify_data.email,
        VerificationCode.code == verify_data.code,
        VerificationCode.used == False,
        VerificationCode.expires_at > datetime.utcnow()
    ).first()

    if not code_record:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    # Find user
    user = db.query(User).filter(User.email == verify_data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Mark code as used and verify user
    code_record.used = True
    user.is_verified = True
    db.commit()

    return {
        "success": True,
        "message": "Email verified successfully",
        "data": {
            "user_id": user.id,
            "email": user.email,
            "verified": True
        }
    }


@router.post("/login")
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """Login user"""

    # Find user
    user = db.query(User).filter(User.email == login_data.email).first()

    if not user or not verify_password(login_data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email not verified. Please verify your email first.")

    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})

    return {
        "success": True,
        "message": "Login successful",
        "data": {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "fullname": user.fullname
            }
        }
    }


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return {
        "success": True,
        "message": "User info retrieved",
        "data": {
            "id": current_user.id,
            "email": current_user.email,
            "fullname": current_user.fullname,
            "is_verified": current_user.is_verified,
            "created_at": current_user.created_at.isoformat()
        }
    }


@router.post("/forgot-password")
def forgot_password(forgot_data: ForgotPassword, db: Session = Depends(get_db)):
    """Request password reset with Resend email service"""

    # Find user
    user = db.query(User).filter(User.email == forgot_data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email not found")

    # Delete old reset codes
    db.query(VerificationCode).filter(
        VerificationCode.email == forgot_data.email,
        VerificationCode.used == False
    ).delete()
    db.commit()

    # Generate reset code
    code = generate_verification_code()
    verification = VerificationCode(
        email=forgot_data.email,
        code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=15),
        used=False
    )
    db.add(verification)
    db.commit()

    # Send reset email via Resend
    email_result = resend_service.send_password_reset_email(forgot_data.email, user.fullname, code)

    return {
        "success": True,
        "message": "Password reset code sent successfully" if email_result[
            "success"] else "Reset code generated, but email sending failed",
        "data": {
            "email": forgot_data.email,
            "email_sent": email_result["success"],
            "email_provider": email_result.get("provider", "Resend"),
            "email_details": email_result
        }
    }


@router.post("/reset-password")
def reset_password(reset_data: ResetPassword, db: Session = Depends(get_db)):
    """Reset password with code"""

    # Find valid reset code
    code_record = db.query(VerificationCode).filter(
        VerificationCode.email == reset_data.email,
        VerificationCode.code == reset_data.code,
        VerificationCode.used == False,
        VerificationCode.expires_at > datetime.utcnow()
    ).first()

    if not code_record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")

    # Find user
    user = db.query(User).filter(User.email == reset_data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update password and mark code as used
    user.password = hash_password(reset_data.new_password)
    code_record.used = True
    db.commit()

    return {
        "success": True,
        "message": "Password reset successfully",
        "data": {
            "email": reset_data.email
        }
    }


@router.post("/resend-code")
def resend_verification_code(email_data: ForgotPassword, db: Session = Depends(get_db)):
    """Resend verification code via Resend email service"""

    # Find user
    user = db.query(User).filter(User.email == email_data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email not found")

    if user.is_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    # Delete old codes
    db.query(VerificationCode).filter(
        VerificationCode.email == email_data.email,
        VerificationCode.used == False
    ).delete()
    db.commit()

    # Generate new code
    code = generate_verification_code()
    verification = VerificationCode(
        email=email_data.email,
        code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
        used=False
    )
    db.add(verification)
    db.commit()

    # Send email via Resend
    email_result = resend_service.send_verification_email(email_data.email, user.fullname, code)

    return {
        "success": True,
        "message": "Verification code resent successfully" if email_result[
            "success"] else "Code generated, but email sending failed",
        "data": {
            "email": email_data.email,
            "email_sent": email_result["success"],
            "email_provider": email_result.get("provider", "Resend"),
            "email_details": email_result
        }
    }


# ==================
# TEST ENDPOINTS
# ==================

@router.get("/smtp-test")
def test_smtp():
    """Test Resend email service configuration"""
    result = resend_service.test_connection()
    return {
        "success": result["success"],
        "message": result.get("message", result.get("error", "Unknown error")),
        "data": result
    }


@router.get("/email-service-info")
def get_email_service_info():
    """Get Resend email service information"""
    return {
        "success": True,
        "data": {
            "provider": "Resend",
            "from_email": resend_service.from_email,
            "from_name": resend_service.from_name,
            "api_configured": bool(resend_service.api_key),
            "benefits": [
                "3,000 emails/month free",
                "No phone verification required",
                "High deliverability rates",
                "Simple API integration",
                "Works on any server"
            ],
            "setup_url": "https://resend.com"
        }
    }