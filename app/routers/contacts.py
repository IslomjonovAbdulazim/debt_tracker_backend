from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List

from app.database import get_db, User, Contact, Debt
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
    """Get all contacts for user with debt summary"""
    contacts = db.query(Contact).filter(Contact.user_id == current_user.id).all()

    contact_list = []
    for contact in contacts:
        # Calculate debt summary for this contact
        debts = db.query(Debt).filter(Debt.contact_id == contact.id).all()

        i_owe = sum(debt.amount for debt in debts if debt.is_my_debt and not debt.is_paid)
        they_owe = sum(debt.amount for debt in debts if not debt.is_my_debt and not debt.is_paid)
        total_debts = len([d for d in debts if not d.is_paid])

        contact_list.append({
            "id": contact.id,
            "name": contact.name,
            "phone": contact.phone,
            "created_at": contact.created_at.isoformat(),
            "debt_summary": {
                "i_owe_them": i_owe,
                "they_owe_me": they_owe,
                "net_balance": they_owe - i_owe,  # Positive = they owe me more
                "active_debts_count": total_debts
            }
        })

    return success_response(
        f"Retrieved {len(contact_list)} contacts",
        {
            "contacts": contact_list,
            "total_count": len(contact_list)
        }
    )


@router.get("/{contact_id}")
def get_contact(
        contact_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get specific contact by ID"""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()

    if not contact:
        error_response("Contact not found", status_code=status.HTTP_404_NOT_FOUND)

    # Get all debts for this contact
    debts = db.query(Debt).filter(Debt.contact_id == contact.id).all()
    debt_list = []

    for debt in debts:
        debt_list.append({
            "id": debt.id,
            "amount": debt.amount,
            "description": debt.description,
            "is_paid": debt.is_paid,
            "is_my_debt": debt.is_my_debt,
            "created_at": debt.created_at.isoformat()
        })

    return success_response(
        "Contact retrieved successfully",
        {
            "id": contact.id,
            "name": contact.name,
            "phone": contact.phone,
            "created_at": contact.created_at.isoformat(),
            "debts": debt_list
        }
    )


@router.put("/{contact_id}")
def update_contact(
        contact_id: int,
        contact_data: ContactUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Update contact"""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()

    if not contact:
        error_response("Contact not found", status_code=status.HTTP_404_NOT_FOUND)

    # Check if phone number conflicts with another contact
    if contact_data.phone != contact.phone:
        existing = db.query(Contact).filter(
            Contact.user_id == current_user.id,
            Contact.phone == contact_data.phone,
            Contact.id != contact_id
        ).first()

        if existing:
            error_response("Another contact with this phone already exists", status_code=status.HTTP_400_BAD_REQUEST)

    # Update contact
    contact.name = contact_data.name
    contact.phone = contact_data.phone
    db.commit()
    db.refresh(contact)

    return success_response(
        "Contact updated successfully",
        {
            "id": contact.id,
            "name": contact.name,
            "phone": contact.phone,
            "created_at": contact.created_at.isoformat()
        }
    )


@router.delete("/{contact_id}")
def delete_contact(
        contact_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Delete contact and all associated debts"""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()

    if not contact:
        error_response("Contact not found", status_code=status.HTTP_404_NOT_FOUND)

    # Count debts that will be deleted
    debt_count = db.query(Debt).filter(Debt.contact_id == contact.id).count()

    # Delete contact (debts will be cascade deleted)
    db.delete(contact)
    db.commit()

    return success_response(
        "Contact deleted successfully",
        {
            "deleted_contact": {
                "id": contact.id,
                "name": contact.name,
                "phone": contact.phone
            },
            "deleted_debts_count": debt_count
        }
    )