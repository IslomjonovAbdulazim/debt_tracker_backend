# main.py
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db, create_tables
from app.routers import auth, contacts
from datetime import datetime

# Create all database tables when app starts
create_tables()

# Create FastAPI app
app = FastAPI(
    title="Debt Tracker API",
    description="API for managing personal debts and contacts",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Include routers
app.include_router(auth.router)
app.include_router(contacts.router)

# Root endpoint for health check and API info
@app.get("/")
def read_root():
    """API health check and basic information"""
    return {
        "message": "Debt Tracker API is running!",
        "status": "healthy",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

# Better health check endpoint
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Comprehensive health check including database connectivity"""
    try:
        # Test database connection (SQLAlchemy 2.0+ compatible)
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "services": {
                "api": "running",
                "database": "connected",
                "email": "configured"
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "database": "disconnected",
            "error": str(e)
        }