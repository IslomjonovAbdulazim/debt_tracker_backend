# app/models/responses.py
from pydantic import BaseModel
from typing import Optional, Any, Dict, List
from datetime import datetime


class ApiResponse(BaseModel):
    """Standard API response format"""
    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[List[str]] = None
    timestamp: datetime = datetime.utcnow()

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    """Paginated response format"""
    success: bool = True
    message: str
    data: List[Any]
    pagination: Dict[str, Any]
    timestamp: datetime = datetime.utcnow()


class ErrorResponse(BaseModel):
    """Error response format"""
    success: bool = False
    message: str
    errors: List[str]
    error_code: Optional[str] = None
    timestamp: datetime = datetime.utcnow()


# Auth specific responses
class LoginResponse(BaseModel):
    """Login success response"""
    success: bool = True
    message: str = "Login successful"
    data: Dict[str, Any]  # Contains token info and user data
    timestamp: datetime = datetime.utcnow()


class RegisterResponse(BaseModel):
    """Registration response"""
    success: bool = True
    message: str
    data: Dict[str, Any]  # Contains user data and email status
    timestamp: datetime = datetime.utcnow()


class VerificationResponse(BaseModel):
    """Email/code verification response"""
    success: bool = True
    message: str
    data: Dict[str, Any]
    timestamp: datetime = datetime.utcnow()


# Contact specific responses
class ContactResponse(BaseModel):
    """Single contact response"""
    success: bool = True
    message: str
    data: Dict[str, Any]  # Contact data
    timestamp: datetime = datetime.utcnow()


class ContactListResponse(BaseModel):
    """Contact list response"""
    success: bool = True
    message: str
    data: List[Dict[str, Any]]  # List of contacts
    count: int
    timestamp: datetime = datetime.utcnow()


# Generic success response
class SuccessResponse(BaseModel):
    """Generic success response"""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = datetime.utcnow()