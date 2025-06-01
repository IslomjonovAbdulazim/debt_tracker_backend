# app/routers/contacts.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db, User, Contact
from app.models import ContactCreate, ContactResponse
from app.services.auth_service import get_current_user

# Create router
router = APIRouter(prefix="/contacts", tags=["Contacts"])


@router.post("/", response_model=ContactResponse)
def create_contact(
        contact_data: ContactCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Create a new contact for the authenticated user"""

    new_contact = Contact(
        fullname=contact_data.fullname,
        phone_number=contact_data.phone_number,
        user_id=current_user.id  # Use authenticated user's ID
    )

    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)

    return new_contact


@router.get("/", response_model=List[ContactResponse])
def get_contacts(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get all contacts for the authenticated user"""

    contacts = db.query(Contact).filter(Contact.user_id == current_user.id).all()
    return contacts


@router.get("/{contact_id}", response_model=ContactResponse)
def get_contact(
        contact_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get a specific contact by ID (only if owned by current user)"""

    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )

    return contact


@router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(
        contact_id: int,
        contact_data: ContactCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Update a contact (only if owned by current user)"""

    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )

    # Update contact fields
    contact.fullname = contact_data.fullname
    contact.phone_number = contact_data.phone_number

    db.commit()
    db.refresh(contact)

    return contact


@router.delete("/{contact_id}")
def delete_contact(
        contact_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Delete a contact and all associated debts (only if owned by current user)"""

    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )

    db.delete(contact)
    db.commit()

    return {
        "message": "Contact deleted successfully",
        "contact_id": contact_id
    }