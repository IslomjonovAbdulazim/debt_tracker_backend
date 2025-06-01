from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from app.database import get_db, User, Contact
from app.auth import get_current_user
from app.responses import success_response, error_response

router = APIRouter()


# Pydantic models
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
    debt_summary: dict
    created_at: str


@router.post("/")
def create_contact(
        contact_data: ContactCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Create new contact"""
    # Check if contact already exists for this user
    existing = db.query(Contact).filter(
        Contact.user_id == current_user.id,
        Contact.phone == contact_data.phone
    ).first()

    if existing:
        error_response("Contact with this phone already exists", status_code=status.HTTP_400_BAD_REQUEST)

    # Create contact
    contact = Contact(
        name=contact_data.name,
        phone=contact_data.phone,
        user_id=current_user.id
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    return success_response(
        "Contact created successfully",
        {
            "id": contact.id,
            "name": contact.name,
            "phone": contact.phone,
            "created_at": contact.created_at.isoformat()
        },
        status_code=201
    )


@router.get("/")
def get_contacts(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get all contacts for user"""
    contacts = db.query(Contact).filter(Contact.user_id == current_user.id).all()