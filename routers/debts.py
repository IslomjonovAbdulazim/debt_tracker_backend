from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db, User, Contact, Debt
from models import DebtCreate, DebtUpdate, DebtResponse
from routers.auth import get_current_user

router = APIRouter()


@router.post("/", response_model=dict)
def create_debt(
        debt_data: DebtCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Create a new debt"""

    # Verify contact belongs to current user
    contact = db.query(Contact).filter(
        Contact.id == debt_data.contact_id,
        Contact.user_id == current_user.id
    ).first()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Validate amount
    if debt_data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")

    # Create debt
    debt = Debt(
        contact_id=debt_data.contact_id,
        amount=debt_data.amount,
        description=debt_data.description,
        is_my_debt=debt_data.is_my_debt,
        is_paid=False
    )

    db.add(debt)
    db.commit()
    db.refresh(debt)

    return {
        "success": True,
        "message": "Debt created successfully",
        "data": {
            "id": debt.id,
            "contact_id": debt.contact_id,
            "contact_name": contact.name,
            "amount": debt.amount,
            "description": debt.description,
            "is_paid": debt.is_paid,
            "is_my_debt": debt.is_my_debt,
            "created_at": debt.created_at.isoformat()
        }
    }


@router.get("/", response_model=dict)
def get_debts(
        is_paid: Optional[bool] = Query(None, description="Filter by paid status"),
        is_my_debt: Optional[bool] = Query(None, description="Filter by debt type"),
        contact_id: Optional[int] = Query(None, description="Filter by contact"),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get all debts for user with optional filters"""

    # Base query - only debts for contacts owned by current user
    query = db.query(Debt).join(Contact).filter(Contact.user_id == current_user.id)

    # Apply filters
    if is_paid is not None:
        query = query.filter(Debt.is_paid == is_paid)

    if is_my_debt is not None:
        query = query.filter(Debt.is_my_debt == is_my_debt)

    if contact_id is not None:
        # Verify contact belongs to user
        contact = db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.user_id == current_user.id
        ).first()

        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")

        query = query.filter(Debt.contact_id == contact_id)

    debts = query.all()

    debt_list = []
    for debt in debts:
        debt_list.append({
            "id": debt.id,
            "contact_id": debt.contact_id,
            "contact_name": debt.contact.name,
            "contact_phone": debt.contact.phone,
            "amount": debt.amount,
            "description": debt.description,
            "is_paid": debt.is_paid,
            "is_my_debt": debt.is_my_debt,
            "created_at": debt.created_at.isoformat()
        })

    return {
        "success": True,
        "message": f"Retrieved {len(debt_list)} debts",
        "data": {
            "debts": debt_list,
            "total_count": len(debt_list),
            "filters": {
                "is_paid": is_paid,
                "is_my_debt": is_my_debt,
                "contact_id": contact_id
            }
        }
    }


@router.get("/overview", response_model=dict)
def get_debt_overview(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get debt overview/summary for user"""

    # Get all debts for user's contacts
    debts = db.query(Debt).join(Contact).filter(Contact.user_id == current_user.id).all()

    # Calculate totals
    i_owe_total = sum(debt.amount for debt in debts if debt.is_my_debt and not debt.is_paid)
    they_owe_total = sum(debt.amount for debt in debts if not debt.is_my_debt and not debt.is_paid)
    paid_debts = len([debt for debt in debts if debt.is_paid])
    active_debts = len([debt for debt in debts if not debt.is_paid])

    # Net balance (positive = people owe me more, negative = I owe more)
    net_balance = they_owe_total - i_owe_total

    # Recent debts (last 5)
    recent_debts = db.query(Debt).join(Contact).filter(
        Contact.user_id == current_user.id
    ).order_by(Debt.created_at.desc()).limit(5).all()

    recent_list = []
    for debt in recent_debts:
        recent_list.append({
            "id": debt.id,
            "contact_name": debt.contact.name,
            "amount": debt.amount,
            "description": debt.description,
            "is_my_debt": debt.is_my_debt,
            "is_paid": debt.is_paid,
            "created_at": debt.created_at.isoformat()
        })

    return {
        "success": True,
        "message": "Debt overview retrieved successfully",
        "data": {
            "summary": {
                "i_owe": i_owe_total,
                "they_owe_me": they_owe_total,
                "net_balance": net_balance,
                "active_debts_count": active_debts,
                "paid_debts_count": paid_debts,
                "total_contacts": db.query(Contact).filter(Contact.user_id == current_user.id).count()
            },
            "recent_debts": recent_list
        }
    }


@router.get("/{debt_id}", response_model=dict)
def get_debt(
        debt_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get specific debt by ID"""

    debt = db.query(Debt).join(Contact).filter(
        Debt.id == debt_id,
        Contact.user_id == current_user.id
    ).first()

    if not debt:
        raise HTTPException(status_code=404, detail="Debt not found")

    return {
        "success": True,
        "message": "Debt retrieved successfully",
        "data": {
            "id": debt.id,
            "contact_id": debt.contact_id,
            "contact_name": debt.contact.name,
            "contact_phone": debt.contact.phone,
            "amount": debt.amount,
            "description": debt.description,
            "is_paid": debt.is_paid,
            "is_my_debt": debt.is_my_debt,
            "created_at": debt.created_at.isoformat()
        }
    }


@router.put("/{debt_id}", response_model=dict)
def update_debt(
        debt_id: int,
        debt_data: DebtUpdate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Update debt"""

    debt = db.query(Debt).join(Contact).filter(
        Debt.id == debt_id,
        Contact.user_id == current_user.id
    ).first()

    if not debt:
        raise HTTPException(status_code=404, detail="Debt not found")

    # Validate amount
    if debt_data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")

    # Update debt
    debt.amount = debt_data.amount
    debt.description = debt_data.description
    debt.is_paid = debt_data.is_paid
    debt.is_my_debt = debt_data.is_my_debt

    db.commit()
    db.refresh(debt)

    return {
        "success": True,
        "message": "Debt updated successfully",
        "data": {
            "id": debt.id,
            "contact_name": debt.contact.name,
            "amount": debt.amount,
            "description": debt.description,
            "is_paid": debt.is_paid,
            "is_my_debt": debt.is_my_debt,
            "created_at": debt.created_at.isoformat()
        }
    }


@router.delete("/{debt_id}", response_model=dict)
def delete_debt(
        debt_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Delete debt"""

    debt = db.query(Debt).join(Contact).filter(
        Debt.id == debt_id,
        Contact.user_id == current_user.id
    ).first()

    if not debt:
        raise HTTPException(status_code=404, detail="Debt not found")

    # Store debt info before deletion
    debt_info = {
        "id": debt.id,
        "contact_name": debt.contact.name,
        "amount": debt.amount,
        "description": debt.description,
        "is_my_debt": debt.is_my_debt
    }

    db.delete(debt)
    db.commit()

    return {
        "success": True,
        "message": "Debt deleted successfully",
        "data": {
            "deleted_debt": debt_info
        }
    }


@router.patch("/{debt_id}/pay", response_model=dict)
def mark_debt_paid(
        debt_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Mark debt as paid (quick action)"""

    debt = db.query(Debt).join(Contact).filter(
        Debt.id == debt_id,
        Contact.user_id == current_user.id
    ).first()

    if not debt:
        raise HTTPException(status_code=404, detail="Debt not found")

    debt.is_paid = True
    db.commit()

    return {
        "success": True,
        "message": "Debt marked as paid",
        "data": {
            "id": debt.id,
            "contact_name": debt.contact.name,
            "amount": debt.amount,
            "is_paid": debt.is_paid
        }
    }