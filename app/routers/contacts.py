# app/routers/contacts.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db, User, Contact
from app.models import ContactCreate, ContactResponse

# Create router
router = APIRouter(prefix="/contacts", tags=["Contacts"])


@router.post("/", response_model=ContactResponse)
def create_contact(contact_data: ContactCreate, db: Session = Depends(get_db)):
    """Create a new contact"""
    # TODO: Add authentication to get current user
    # For now, we'll use user_id = 1 (placeholder)

    new_contact = Contact(
        fullname=contact_data.fullname,
        phone_number=contact_data.phone_number,
        user_id=1  # TODO: Get from authenticated user
    )

    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)

    return new_contact


@router.get("/", response_model=List[ContactResponse])
def get_contacts(db: Session = Depends(get_db)):
    """Get all contacts for the authenticated user"""
    # TODO: Get current user from authentication
    # For now, we'll use user_id = 1 (placeholder)

    contacts = db.query(Contact).filter(Contact.user_id == 1).all()
    return contacts


@router.delete("/{contact_id}")
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    """Delete a contact and all associated debts"""
    # TODO: Add authentication and ownership check

    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )

    db.delete(contact)
    db.commit()

    return {"message": "Contact deleted successfully"}

# TODO: Add more endpoints:
# - GET /contacts/{contact_id}/debts
# - PUT /contacts/{contact_id} (update contact)