# app/routers/social_auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.services.social_auth_service import (
    generate_state, get_authorization_url, process_social_callback
)
from app.utils.responses import success_response, raise_http_error
from app.config import settings

# Create router
router = APIRouter(prefix="/auth", tags=["Social Authentication"])


@router.get("/google/login")
def google_login():
    """Initiate Google OAuth login"""
    state = generate_state()
    auth_url = get_authorization_url("google", state)

    return success_response(
        message="Google OAuth URL generated",
        data={
            "auth_url": auth_url,
            "state": state,
            "provider": "google",
            "instructions": "Redirect user to auth_url, then handle callback"
        }
    )


@router.get("/github/login")
def github_login():
    """Initiate GitHub OAuth login"""
    state = generate_state()
    auth_url = get_authorization_url("github", state)

    return success_response(
        message="GitHub OAuth URL generated",
        data={
            "auth_url": auth_url,
            "state": state,
            "provider": "github",
            "instructions": "Redirect user to auth_url, then handle callback"
        }
    )


@router.get("/google/callback")
async def google_callback(
        code: str,
        state: Optional[str] = None,
        error: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """Handle Google OAuth callback"""

    if error:
        # Redirect to frontend with error
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/error?error={error}&provider=google"
        )

    if not code:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/error?error=missing_code&provider=google"
        )

    try:
        # Process the callback
        result = await process_social_callback("google", code, state, db)

        # Redirect to frontend with token
        auth_params = f"token={result['access_token']}&provider=google&new_user={result['is_new_user']}"
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/success?{auth_params}"
        )

    except Exception as e:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/error?error=auth_failed&provider=google&details={str(e)}"
        )


@router.get("/github/callback")
async def github_callback(
        code: str,
        state: Optional[str] = None,
        error: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """Handle GitHub OAuth callback"""

    if error:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/error?error={error}&provider=github"
        )

    if not code:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/error?error=missing_code&provider=github"
        )

    try:
        # Process the callback
        result = await process_social_callback("github", code, state, db)

        # Redirect to frontend with token
        auth_params = f"token={result['access_token']}&provider=github&new_user={result['is_new_user']}"
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/success?{auth_params}"
        )

    except Exception as e:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/error?error=auth_failed&provider=github&details={str(e)}"
        )


# Alternative API endpoints (for mobile apps or SPA)
@router.post("/google/exchange")
async def google_exchange_code(
        code: str,
        state: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """Exchange Google auth code for JWT token (API endpoint)"""

    try:
        result = await process_social_callback("google", code, state, db)

        message = "Google authentication successful"
        if result["is_new_user"]:
            message = "Account created via Google authentication"

        return success_response(
            message=message,
            data={
                "access_token": result["access_token"],
                "token_type": result["token_type"],
                "user": result["user"],
                "is_new_user": result["is_new_user"],
                "provider": "google"
            }
        )

    except Exception as e:
        raise_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Google authentication failed",
            errors=[str(e)],
            error_code="GOOGLE_AUTH_FAILED"
        )


@router.post("/github/exchange")
async def github_exchange_code(
        code: str,
        state: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """Exchange GitHub auth code for JWT token (API endpoint)"""

    try:
        result = await process_social_callback("github", code, state, db)

        message = "GitHub authentication successful"
        if result["is_new_user"]:
            message = "Account created via GitHub authentication"

        return success_response(
            message=message,
            data={
                "access_token": result["access_token"],
                "token_type": result["token_type"],
                "user": result["user"],
                "is_new_user": result["is_new_user"],
                "provider": "github"
            }
        )

    except Exception as e:
        raise_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="GitHub authentication failed",
            errors=[str(e)],
            error_code="GITHUB_AUTH_FAILED"
        )


@router.get("/providers")
def get_available_providers():
    """Get list of available OAuth providers"""

    providers = []

    if settings.GOOGLE_CLIENT_ID:
        providers.append({
            "name": "google",
            "display_name": "Google",
            "login_url": "/auth/google/login",
            "available": True
        })

    if settings.GITHUB_CLIENT_ID:
        providers.append({
            "name": "github",
            "display_name": "GitHub",
            "login_url": "/auth/github/login",
            "available": True
        })

    return success_response(
        message="Available OAuth providers retrieved",
        data={
            "providers": providers,
            "count": len(providers),
            "email_auth_available": True
        }
    )