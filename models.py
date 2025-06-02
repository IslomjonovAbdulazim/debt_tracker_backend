from pydantic import BaseModel, EmailStr
from typing import Optional


# ==================
# AUTH MODELS
# ==================

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


# ==================
# CONTACT MODELS
# ==================

class ContactCreate(BaseModel):
    name: str
    phone: str


class ContactUpdate(BaseModel):
    name: str
    phone: str


class ContactResponse(BaseModel):
    id: int
    name: str
    phone: str
    created_at: str

    class Config:
        from_attributes = True


# ==================
# DEBT MODELS
# ==================

class DebtCreate(BaseModel):
    contact_id: int
    amount: float
    description: str
    is_my_debt: bool  # True = I owe them, False = they owe me


class DebtUpdate(BaseModel):
    amount: float
    description: str
    is_paid: bool
    is_my_debt: bool


class DebtResponse(BaseModel):
    id: int
    amount: float
    description: str
    is_paid: bool
    is_my_debt: bool
    contact_id: int
    created_at: str

    class Config:
        from_attributes = True


# ==================
# RESPONSE MODELS
# ==================

class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[dict] = None


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error: Optional[str] = None