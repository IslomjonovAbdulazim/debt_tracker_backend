from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db, User, Contact, Debt
from models import ContactCreate, ContactUpdate, ContactResponse
from routers.auth import get_current_user

router = APIRouter()


@router.post("/", response_model=dict)
def create_contact(
        contact_data: ContactCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Create a new contact"""

    # Check if contact with this phone already exists for this user
    existing_contact = db.query(Contact).filter(
        Contact.user_id == current_user.id,
        Contact.phone == contact_data.phone
    ).first()

    if existing_contact:
        raise HTTPException(status_code=400, detail="Contact with this phone number already exists")

    # Create new contact
    contact = Contact(
        name=contact_data.name,
        phone=contact_data.phone,
        user_id=current_user.id
    )

    db.add(contact)
    db.commit()
    db.refresh(contact)

    return {
        "success": True,
        "message": "Contact created successfully",
        "data": {
            "id": contact.id,
            "name": contact.name,
            "phone": contact.phone,
            "created_at": contact.created_at.isoformat()
        }
    }


@router.get("/", response_model=dict)
def get_contacts(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get all contacts for the current user"""

    contacts = db.query(Contact).filter(Contact.user_id == current_user.id).all()

    contact_list = []
    for contact in contacts:
        # Calculate debt summary for this contact
        debts = db.query(Debt).filter(Debt.contact_id == contact.id).all()

        # Calculate amounts
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

    return {
        "success": True,
        "message": f"Retrieved {len(contact_list)} contacts",
        "data": {
            "contacts": contact_list,
            "total_count": len(contact_list)
        }
    }


@router.get("/{contact_id}", response_model=dict)
def get_contact(
        contact_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get a specific contact by ID"""

    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

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

    return {
        "success": True,
        "message": "Contact retrieved successfully",
        "data": {
            "id": contact.id,
            "name": contact.name,
            "phone": contact.phone,
            "created_at": contact.created_at.isoformat(),
            "debts": debt_list
        }
    }


@router.put("/{contact_id}", response_model=dict)
def update_contact(
        contact_id: int,
        contact_data: ContactUpdate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Update a contact"""

    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Check if new phone number conflicts with another contact
    if contact_data.phone != contact.phone:
        existing_contact = db.query(Contact).filter(
            Contact.user_id == current_user.id,
            Contact.phone == contact_data.phone,
            Contact.id != contact_id
        ).first()

        if existing_contact:
            raise HTTPException(status_code=400, detail="Another contact with this phone number already exists")

    # Update contact
    contact.name = contact_data.name
    contact.phone = contact_data.phone

    db.commit()
    db.refresh(contact)

    return {
        "success": True,
        "message": "Contact updated successfully",
        "data": {
            "id": contact.id,
            "name": contact.name,
            "phone": contact.phone,
            "created_at": contact.created_at.isoformat()
        }
    }


@router.delete("/{contact_id}", response_model=dict)
def delete_contact(
        contact_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Delete a contact and all associated debts"""

    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Count debts that will be deleted
    debt_count = db.query(Debt).filter(Debt.contact_id == contact.id).count()

    # Store contact info before deletion
    contact_info = {
        "id": contact.id,
        "name": contact.name,
        "phone": contact.phone
    }

    # Delete contact (debts will be cascade deleted)
    db.delete(contact)
    db.commit()

    return {
        "success": True,
        "message": "Contact deleted successfully",
        "data": {
            "deleted_contact": contact_info,
            "deleted_debts_count": debt_count
        }
    }