# app/services/social_auth_service.py
import httpx
import secrets
from typing import Optional, Dict, Any
from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import User, SocialAccount
from app.services.auth_service import create_user_token
from app.models.social_auth import SocialUserInfo

# Initialize OAuth
oauth = OAuth()

# Configure Google OAuth
oauth.register(
    name='google',
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# Configure GitHub OAuth
oauth.register(
    name='github',
    client_id=settings.GITHUB_CLIENT_ID,
    client_secret=settings.GITHUB_CLIENT_SECRET,
    access_token_url='https://github.com/login/oauth/access_token',
    authorize_url='https://github.com/login/oauth/authorize',
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'}
)


def generate_state() -> str:
    """Generate secure state parameter for OAuth"""
    return secrets.token_urlsafe(32)


def get_authorization_url(provider: str, state: str) -> str:
    """Get OAuth authorization URL"""
    if provider == "google":
        redirect_uri = settings.GOOGLE_REDIRECT_URI
        return f"https://accounts.google.com/o/oauth2/auth?client_id={settings.GOOGLE_CLIENT_ID}&redirect_uri={redirect_uri}&scope=openid email profile&response_type=code&state={state}"

    elif provider == "github":
        redirect_uri = settings.GITHUB_REDIRECT_URI
        return f"https://github.com/login/oauth/authorize?client_id={settings.GITHUB_CLIENT_ID}&redirect_uri={redirect_uri}&scope=user:email&state={state}"

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}"
        )


async def get_user_info_from_google(access_token: str) -> SocialUserInfo:
    """Get user info from Google API"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get user info from Google"
            )

        data = response.json()
        return SocialUserInfo(
            email=data.get("email"),
            name=data.get("name"),
            avatar_url=data.get("picture"),
            provider="google",
            provider_id=str(data.get("id"))
        )


async def get_user_info_from_github(access_token: str) -> SocialUserInfo:
    """Get user info from GitHub API"""
    async with httpx.AsyncClient() as client:
        # Get user profile
        user_response = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if user_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get user info from GitHub"
            )

        user_data = user_response.json()

        # Get user email (GitHub might not provide it in profile)
        email_response = await client.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        emails = email_response.json() if email_response.status_code == 200 else []
        primary_email = next((e["email"] for e in emails if e.get("primary", False)), None)

        if not primary_email:
            primary_email = user_data.get("email")

        if not primary_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to get email from GitHub. Please make your email public."
            )

        return SocialUserInfo(
            email=primary_email,
            name=user_data.get("name") or user_data.get("login"),
            avatar_url=user_data.get("avatar_url"),
            provider="github",
            provider_id=str(user_data.get("id"))
        )


async def exchange_code_for_token(provider: str, code: str) -> str:
    """Exchange authorization code for access token"""
    if provider == "google":
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI
                }
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange code for token"
                )

            data = response.json()
            return data.get("access_token")

    elif provider == "github":
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code
                },
                headers={"Accept": "application/json"}
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange code for token"
                )

            data = response.json()
            return data.get("access_token")

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}"
        )


def find_or_create_user(db: Session, user_info: SocialUserInfo) -> tuple[User, bool]:
    """Find existing user or create new one from social auth"""

    # First, try to find user by email
    existing_user = db.query(User).filter(User.email == user_info.email).first()

    if existing_user:
        # User exists, check if this social account is already linked
        social_account = db.query(SocialAccount).filter(
            SocialAccount.user_id == existing_user.id,
            SocialAccount.provider == user_info.provider
        ).first()

        if not social_account:
            # Link this social account to existing user
            social_account = SocialAccount(
                user_id=existing_user.id,
                provider=user_info.provider,
                provider_id=user_info.provider_id,
                provider_email=user_info.email
            )
            db.add(social_account)

        # Update user info from social provider
        if user_info.avatar_url:
            existing_user.avatar_url = user_info.avatar_url

        # Mark email as verified for social auth
        existing_user.is_email_verified = True

        db.commit()
        return existing_user, False

    else:
        # Create new user
        new_user = User(
            email=user_info.email,
            fullname=user_info.name,
            is_email_verified=True,  # Social auth emails are pre-verified
            avatar_url=user_info.avatar_url,
            auth_provider=user_info.provider,
            provider_id=user_info.provider_id
        )

        db.add(new_user)
        db.flush()  # Get the user ID

        # Create social account record
        social_account = SocialAccount(
            user_id=new_user.id,
            provider=user_info.provider,
            provider_id=user_info.provider_id,
            provider_email=user_info.email
        )

        db.add(social_account)
        db.commit()

        return new_user, True


async def process_social_callback(
        provider: str,
        code: str,
        state: str,
        db: Session
) -> Dict[str, Any]:
    """Process OAuth callback and return user data"""

    # Exchange code for access token
    access_token = await exchange_code_for_token(provider, code)

    # Get user info from provider
    if provider == "google":
        user_info = await get_user_info_from_google(access_token)
    elif provider == "github":
        user_info = await get_user_info_from_github(access_token)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}"
        )

    # Find or create user
    user, is_new_user = find_or_create_user(db, user_info)

    # Create JWT token
    token_data = create_user_token(user)

    return {
        "access_token": token_data["access_token"],
        "token_type": token_data["token_type"],
        "user": token_data["user"],
        "is_new_user": is_new_user,
        "provider": provider
    }