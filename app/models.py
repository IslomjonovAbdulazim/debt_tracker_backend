# app/models.py
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


# User models
class UserCreate(BaseModel):
    email: str
    password: str
    fullname: str


class UserResponse(BaseModel):
    id: int
    email: str
    fullname: str
    created_at: datetime

    class Config:
        from_attributes = True  # Allows conversion from SQLAlchemy models


class UserLogin(BaseModel):
    email: str
    password: str


# Contact models
class ContactCreate(BaseModel):
    fullname: str
    phone_number: str


class ContactResponse(BaseModel):
    id: int
    fullname: str
    phone_number: str
    created_at: datetime

    class Config:
        from_attributes = True


# Debt models
class DebtCreate(BaseModel):
    contact_id: int
    debt_amount: float
    description: str
    due_date: datetime
    is_paid: bool = False
    is_my_debt: bool  # True = I owe them, False = they owe me


class DebtResponse(BaseModel):
    id: int
    debt_amount: float
    description: str
    due_date: datetime
    is_paid: bool
    is_my_debt: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Authentication models
class ForgotPassword(BaseModel):
    email: str


class VerifyEmail(BaseModel):
    email: str
    code: str


class VerifyPasswordReset(BaseModel):
    email: str
    reset_code: str


class ResetPassword(BaseModel):
    email: str
    reset_code: str
    new_password: str


class ResendCode(BaseModel):
    email: str
    code_type: str  # "email_verification" or "password_reset"


class OverviewResponse(BaseModel):
    i_owe: float
    they_owe: float
    overdue: int
    active_debts: int