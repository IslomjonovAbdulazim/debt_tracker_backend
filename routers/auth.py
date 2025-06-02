from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import asyncio

from database import get_db, User, VerificationCode
from models import UserRegister, UserLogin, VerifyCode, ForgotPassword, ResetPassword
from auth_utils import hash_password, verify_password, create_access_token, verify_token, generate_code
from email_service import email_service

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
# OPTIMIZED AUTH ROUTES
# ==================

@router.post("/register")
async def register(
    user_data: UserRegister,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Register a new user with optimized email handling"""

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
    code = generate_code()
    verification = VerificationCode(
        email=user_data.email,
        code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
        used=False
    )
    db.add(verification)
    db.commit()

    # Send email in background (non-blocking)
    background_tasks.add_task(
        send_verification_email_task,
        user_data.email,
        user_data.fullname,
        code
    )

    return {
        "success": True,
        "message": "User registered successfully. Verification code is being sent to your email.",
        "data": {
            "user_id": user.id,
            "email": user.email,
            "email_status": "sending"
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
async def forgot_password(
    forgot_data: ForgotPassword,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Request password reset"""

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
    code = generate_code()
    verification = VerificationCode(
        email=forgot_data.email,
        code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=15),
        used=False
    )
    db.add(verification)
    db.commit()

    # Send reset email in background
    background_tasks.add_task(
        send_password_reset_email_task,
        forgot_data.email,
        user.fullname,
        code
    )

    return {
        "success": True,
        "message": "Password reset code is being sent to your email address",
        "data": {
            "email": forgot_data.email,
            "email_status": "sending"
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
async def resend_verification_code(
    email_data: ForgotPassword,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Resend verification code"""

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
    code = generate_code()
    verification = VerificationCode(
        email=email_data.email,
        code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
        used=False
    )
    db.add(verification)
    db.commit()

    # Send email in background
    background_tasks.add_task(
        send_verification_email_task,
        email_data.email,
        user.fullname,
        code
    )

    return {
        "success": True,
        "message": "Verification code is being resent to your email address",
        "data": {
            "email": email_data.email,
            "email_status": "sending"
        }
    }

# ==================
# BACKGROUND TASKS
# ==================

async def send_verification_email_task(email: str, name: str, code: str):
    """Background task to send verification email"""
    try:
        result = await email_service.send_verification_email(email, name, code)
        print(f"✅ Verification email result for {email}: {result['method']}")
    except Exception as e:
        print(f"❌ Email task error for {email}: {e}")

async def send_password_reset_email_task(email: str, name: str, code: str):
    """Background task to send password reset email"""
    try:
        result = await email_service.send_password_reset_email(email, name, code)
        print(f"✅ Reset email result for {email}: {result['method']}")
    except Exception as e:
        print(f"❌ Email task error for {email}: {e}")

# ==================
# ADMIN ROUTES (Optional)
# ==================

@router.get("/email-queue")
async def get_email_queue():
    """Get queued emails (for debugging)"""
    try:
        import json
        with open("email_queue.json", 'r') as f:
            queue = json.load(f)
        return {"success": True, "data": {"queued_emails": len(queue), "emails": queue}}
    except FileNotFoundError:
        return {"success": True, "data": {"queued_emails": 0, "emails": []}}

@router.post("/retry-emails")
async def retry_queued_emails():
    """Retry sending queued emails"""
    result = await email_service.retry_queued_emails()
    return {"success": True, "data": result}