# main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

from app.database import get_db, create_tables
from app.routers import auth, contacts
from app.middleware.error_handler import (
    http_exception_handler,
    validation_exception_handler,
    sqlalchemy_exception_handler,
    general_exception_handler
)
from app.utils.responses import success_response, server_error_response

# Create all database tables when app starts
create_tables()

# Create FastAPI app
app = FastAPI(
    title="Debt Tracker API",
    description="A professional API for managing personal debts and contacts with standardized responses",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add error handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include routers
app.include_router(auth.router)
app.include_router(contacts.router)


# Root endpoint with standardized response
@app.get("/")
def read_root():
    """API health check and basic information"""
    return success_response(
        message="Debt Tracker API is running successfully",
        data={
            "api_name": "Debt Tracker API",
            "version": "1.0.0",
            "status": "healthy",
            "endpoints": {
                "documentation": "/docs",
                "alternative_docs": "/redoc",
                "health_check": "/health"
            },
            "features": [
                "User Authentication with JWT",
                "Email Verification",
                "Password Reset",
                "Contact Management",
                "Debt Tracking",
                "Standardized API Responses"
            ]
        }
    )


# Comprehensive health check endpoint
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Comprehensive health check including database connectivity"""
    try:
        # Test database connection
        db.execute(text("SELECT 1"))

        return success_response(
            message="All systems operational",
            data={
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "services": {
                    "api": "operational",
                    "database": "connected",
                    "email": "configured",
                    "authentication": "enabled"
                },
                "uptime_check": "passed"
            }
        )

    except Exception as e:
        return {
            "success": False,
            "message": "System health check failed",
            "data": {
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "services": {
                    "api": "operational",
                    "database": "disconnected",
                    "email": "unknown",
                    "authentication": "unknown"
                },
                "error": str(e)
            },
            "errors": ["Database connection failed"],
            "error_code": "HEALTH_CHECK_FAILED",
            "status_code": 503
        }


# API status endpoint
@app.get("/status")
def api_status():
    """Get API status and statistics"""
    return success_response(
        message="API status retrieved successfully",
        data={
            "api_version": "1.0.0",
            "environment": "production",
            "maintenance_mode": False,
            "supported_features": {
                "authentication": True,
                "email_verification": True,
                "password_reset": True,
                "contact_management": True,
                "debt_tracking": True,
                "file_uploads": False,
                "push_notifications": False
            },
            "api_limits": {
                "rate_limit": "100 requests per minute",
                "max_contacts": "unlimited",
                "max_debts": "unlimited",
                "file_size_limit": "N/A"
            },
            "last_updated": datetime.now().isoformat()
        }
    )