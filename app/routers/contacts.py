# app/routers/contacts.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db, User, Contact
from app.models import ContactCreate, ContactResponse
from app.services.auth_service import get_current_user
from app.utils.responses import success_response, raise_http_error

# Create router
router = APIRouter(prefix="/contacts", tags=["Contacts"])


@router.post("/")
def create_contact(
        contact_data: ContactCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Create a new contact for the authenticated user"""

    # Check if contact with same phone already exists for this user
    existing_contact = db.query(Contact).filter(
        Contact.user_id == current_user.id,
        Contact.phone_number == contact_data.phone_number
    ).first()

    if existing_contact:
        raise_http_error(
            status_code=status.HTTP_409_CONFLICT,
            message="Contact with this phone number already exists",
            error_code="CONTACT_EXISTS"
        )

    new_contact = Contact(
        fullname=contact_data.fullname,
        phone_number=contact_data.phone_number,
        user_id=current_user.id
    )

    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)

    return success_response(
        message="Contact created successfully",
        data={
            "contact": {
                "id": new_contact.id,
                "fullname": new_contact.fullname,
                "phone_number": new_contact.phone_number,
                "created_at": new_contact.created_at.isoformat()
            }
        },
        status_code=201
    )


@router.get("/")
def get_contacts(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get all contacts for the authenticated user"""

    contacts = db.query(Contact).filter(Contact.user_id == current_user.id).all()

    contact_list = []
    for contact in contacts:
        contact_list.append({
            "id": contact.id,
            "fullname": contact.fullname,
            "phone_number": contact.phone_number,
            "created_at": contact.created_at.isoformat()
        })

    return success_response(
        message=f"Retrieved {len(contact_list)} contacts successfully",
        data={
            "contacts": contact_list,
            "count": len(contact_list)
        }
    )


@router.get("/{contact_id}")
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
        raise_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Contact not found",
            error_code="CONTACT_NOT_FOUND"
        )

    return success_response(
        message="Contact retrieved successfully",
        data={
            "contact": {
                "id": contact.id,
                "fullname": contact.fullname,
                "phone_number": contact.phone_number,
                "created_at": contact.created_at.isoformat()
            }
        }
    )


@router.put("/{contact_id}")
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
        raise_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Contact not found",
            error_code="CONTACT_NOT_FOUND"
        )

    # Check if phone number conflicts with another contact
    existing_contact = db.query(Contact).filter(
        Contact.user_id == current_user.id,
        Contact.phone_number == contact_data.phone_number,
        Contact.id != contact_id
    ).first()

    if existing_contact:
        raise_http_error(
            status_code=status.HTTP_409_CONFLICT,
            message="Another contact with this phone number already exists",
            error_code="PHONE_EXISTS"
        )

    # Update contact fields
    contact.fullname = contact_data.fullname
    contact.phone_number = contact_data.phone_number

    db.commit()
    db.refresh(contact)

    return success_response(
        message="Contact updated successfully",
        data={
            "contact": {
                "id": contact.id,
                "fullname": contact.fullname,
                "phone_number": contact.phone_number,
                "created_at": contact.created_at.isoformat()
            }
        }
    )


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
        raise_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Contact not found",
            error_code="CONTACT_NOT_FOUND"
        )

    # Store contact info before deletion
    deleted_contact_info = {
        "id": contact.id,
        "fullname": contact.fullname,
        "phone_number": contact.phone_number
    }

    db.delete(contact)
    db.commit()

    return success_response(
        message="Contact deleted successfully",
        data={
            "deleted_contact": deleted_contact_info,
            "note": "All associated debts were also deleted"
        }
    )