# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta

from app.database import get_db, User, VerificationCode
from app.models import (
    UserCreate, UserResponse, UserLogin, ForgotPassword,
    VerifyEmail, VerifyPasswordReset, ResetPassword, ResendCode
)
from app.services.password_service import hash_password, verify_password, generate_verification_code
from app.services.email_service import send_verification_email, send_password_reset_email
from app.services.auth_service import create_user_token, get_current_user

# Create router
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user account and send verification email"""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Hash the password
    hashed_password = hash_password(user_data.password)

    # Create new user (unverified by default)
    new_user = User(
        email=user_data.email,
        password=hashed_password,
        fullname=user_data.fullname,
        is_email_verified=False  # Account starts as unverified
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Generate verification code
    verification_code_str = generate_verification_code()

    # Store verification code in database
    verification_code = VerificationCode(
        email=user_data.email,
        code=verification_code_str,
        code_type="email_verification",
        expires_at=datetime.now() + timedelta(minutes=10)
    )

    db.add(verification_code)
    db.commit()

    # Send verification email
    try:
        email_result = await send_verification_email(user_data.email, user_data.fullname, verification_code_str)

        return {
            "id": new_user.id,
            "email": new_user.email,
            "fullname": new_user.fullname,
            "created_at": new_user.created_at,
            "message": "Account created! Please check your email to verify your account.",
            "email_sent": email_result["status"] == "success"
        }
    except Exception as e:
        return {
            "id": new_user.id,
            "email": new_user.email,
            "fullname": new_user.fullname,
            "created_at": new_user.created_at,
            "message": "Account created, but verification email failed to send. Use /resend-code endpoint.",
            "email_sent": False
        }


@router.post("/login")
def login_user(login_data: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and receive JWT access token (requires verified email)"""
    # Find user by email
    user = db.query(User).filter(User.email == login_data.email).first()

    if not user or not verify_password(login_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Check if email is verified
    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in. Check your inbox or use /resend-code endpoint."
        )

    # Create JWT token
    token_response = create_user_token(user)

    return {
        "message": "Login successful",
        **token_response
    }


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information"""
    return current_user


@router.post("/logout")
def logout_user(current_user: User = Depends(get_current_user)):
    """Logout user (client should delete the token)"""
    return {
        "message": "Logout successful. Please delete the token from client storage.",
        "user_id": current_user.id
    }


@router.post("/forgot-password")
async def forgot_password(forgot_data: ForgotPassword, db: Session = Depends(get_db)):
    """
    STEP 1: Request password reset code
    - Check if email exists in database
    - Send reset code to user's email
    - User will verify code in /verify-password-reset endpoint
    """
    # Check if user exists
    user = db.query(User).filter(User.email == forgot_data.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email address. Please check your email or register a new account."
        )

    # Generate reset code
    reset_code = generate_verification_code()

    # Store code in database with expiration (15 minutes)
    verification_code = VerificationCode(
        email=forgot_data.email,
        code=reset_code,
        code_type="password_reset",
        expires_at=datetime.now() + timedelta(minutes=15)
    )

    db.add(verification_code)
    db.commit()

    # Send email
    try:
        email_result = await send_password_reset_email(forgot_data.email, user.fullname, reset_code)

        if email_result["status"] == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email. Please try again later or contact support."
            )

        return {
            "message": f"Password reset code has been sent to {forgot_data.email}. Please check your inbox.",
            "status": "success",
            "email": forgot_data.email,
            "expires_in_minutes": 15,
            "next_step": "Use the 6-digit code in /verify-password-reset endpoint"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send reset email. Please try again later."
        )


@router.post("/verify-password-reset")
def verify_password_reset(verify_data: VerifyPasswordReset, db: Session = Depends(get_db)):
    """
    STEP 2: Verify password reset code (security check)
    - Confirms user owns the email before allowing password change
    - Use the 6-digit code from /forgot-password email
    - After verification, user can proceed to /reset-password
    """

    # Find the reset code
    verification_code = db.query(VerificationCode).filter(
        VerificationCode.email == verify_data.email,
        VerificationCode.code == verify_data.reset_code,
        VerificationCode.code_type == "password_reset",
        VerificationCode.is_used == False,
        VerificationCode.expires_at > datetime.now()
    ).first()

    if not verification_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code. Please request a new code using /forgot-password"
        )

    # Check if user exists
    user = db.query(User).filter(User.email == verify_data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # DON'T mark code as used yet - they still need to actually reset password
    # Just confirm the code is valid

    return {
        "message": "Reset code verified successfully! You can now change your password.",
        "status": "verified",
        "email": verify_data.email,
        "next_step": "Use /reset-password endpoint with the same code and your new password"
    }


@router.post("/reset-password")
def reset_password(reset_data: ResetPassword, db: Session = Depends(get_db)):
    """
    STEP 3: Actually reset the password
    - Use the same code from /verify-password-reset
    - Set your new password
    - Must verify code first using /verify-password-reset
    """

    # Find the reset code (must be the same one that was verified)
    verification_code = db.query(VerificationCode).filter(
        VerificationCode.email == reset_data.email,
        VerificationCode.code == reset_data.reset_code,
        VerificationCode.code_type == "password_reset",
        VerificationCode.is_used == False,
        VerificationCode.expires_at > datetime.now()
    ).first()

    if not verification_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code. Please verify your code first using /verify-password-reset"
        )

    # Find user
    user = db.query(User).filter(User.email == reset_data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Validate new password
    if len(reset_data.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )

    # Don't allow same password (basic check)
    if verify_password(reset_data.new_password, user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from your current password"
        )

    # Update password
    user.password = hash_password(reset_data.new_password)

    # NOW mark code as used
    verification_code.is_used = True

    # Invalidate all other unused password reset codes for this email
    other_codes = db.query(VerificationCode).filter(
        VerificationCode.email == reset_data.email,
        VerificationCode.code_type == "password_reset",
        VerificationCode.is_used == False,
        VerificationCode.id != verification_code.id
    ).all()

    for code in other_codes:
        code.is_used = True

    db.commit()

    return {
        "message": "Password reset successfully! You can now login with your new password.",
        "status": "success",
        "user_id": user.id,
        "email": user.email
    }


@router.post("/verify-email")
async def verify_email(verify_data: VerifyEmail, db: Session = Depends(get_db)):
    """
    ONLY FOR EMAIL VERIFICATION (after registration)
    - Use the 6-digit code from registration email
    - Activates your account so you can login
    - NOT used for password resets!
    """
    # Check if user exists
    user = db.query(User).filter(User.email == verify_data.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if already verified
    if user.is_email_verified:
        return {
            "message": "Email already verified",
            "user_id": user.id,
            "email": user.email,
            "status": "already_verified"
        }

    # Find valid verification code
    verification_code = db.query(VerificationCode).filter(
        VerificationCode.email == verify_data.email,
        VerificationCode.code == verify_data.code,
        VerificationCode.code_type == "email_verification",
        VerificationCode.is_used == False,
        VerificationCode.expires_at > datetime.now()
    ).first()

    if not verification_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code"
        )

    # Activate the account
    user.is_email_verified = True
    verification_code.is_used = True

    db.commit()

    return {
        "message": "Email verified successfully! You can now log in.",
        "user_id": user.id,
        "email": user.email,
        "status": "verified"
    }


@router.post("/resend-code")
async def resend_code(resend_data: ResendCode, db: Session = Depends(get_db)):
    """Resend verification code (email verification or password reset)"""

    # Validate code_type
    if resend_data.code_type not in ["email_verification", "password_reset"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid code type. Must be 'email_verification' or 'password_reset'"
        )

    # Check if user exists
    user = db.query(User).filter(User.email == resend_data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email address. Please check your email or register a new account."
        )

    # Check if user has too many recent attempts (rate limiting)
    recent_codes = db.query(VerificationCode).filter(
        VerificationCode.email == resend_data.email,
        VerificationCode.code_type == resend_data.code_type,
        VerificationCode.created_at > datetime.now() - timedelta(minutes=5)
    ).count()

    if recent_codes >= 3:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait 5 minutes before requesting another code."
        )

    # Invalidate old unused codes of the same type
    old_codes = db.query(VerificationCode).filter(
        VerificationCode.email == resend_data.email,
        VerificationCode.code_type == resend_data.code_type,
        VerificationCode.is_used == False
    ).all()

    for old_code in old_codes:
        old_code.is_used = True

    # Generate new code
    new_code = generate_verification_code()

    # Set expiration time based on code type
    if resend_data.code_type == "password_reset":
        expires_in_minutes = 15
    else:  # email_verification
        expires_in_minutes = 10

    # Store new code in database
    verification_code = VerificationCode(
        email=resend_data.email,
        code=new_code,
        code_type=resend_data.code_type,
        expires_at=datetime.now() + timedelta(minutes=expires_in_minutes)
    )

    db.add(verification_code)
    db.commit()

    # Send appropriate email
    try:
        if resend_data.code_type == "password_reset":
            email_result = await send_password_reset_email(resend_data.email, user.fullname, new_code)
            message = "Password reset code resent"
        else:  # email_verification
            email_result = await send_verification_email(resend_data.email, user.fullname, new_code)
            message = "Email verification code resent"

        if email_result["status"] == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email. Please try again later."
            )

        return {
            "message": f"{message} to {resend_data.email}",
            "status": "success",
            "email": resend_data.email,
            "expires_in_minutes": expires_in_minutes
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send email. Please try again later."
        )