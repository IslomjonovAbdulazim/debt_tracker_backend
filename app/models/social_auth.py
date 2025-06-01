# app/models/social_auth.py
from pydantic import BaseModel
from typing import Optional

class SocialAuthCallback(BaseModel):
    """Social auth callback data"""
    code: str
    state: Optional[str] = None

class SocialAuthResponse(BaseModel):
    """Social auth response"""
    success: bool
    message: str
    access_token: Optional[str] = None
    token_type: Optional[str] = None
    user: Optional[dict] = None
    is_new_user: bool = False

class SocialUserInfo(BaseModel):
    """Social platform user info"""
    email: str
    name: str
    avatar_url: Optional[str] = None
    provider: str
    provider_id: str