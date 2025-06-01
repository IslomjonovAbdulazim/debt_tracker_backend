from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import logging

from app.config import settings
from app.database import create_tables
from app.responses import success_response
from app.routers import auth, contacts, debts

# Set up logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create database tables
create_tables()
logger.info("Database tables created/verified")

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="A simple debt tracking API with email verification",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # If detail is already our format, return it
    if isinstance(exc.detail, dict) and "success" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    # Convert simple error to our format
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": str(exc.detail),
            "errors": [],
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(x) for x in error["loc"])
        errors.append(f"{field}: {error['msg']}")

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Validation failed",
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "errors": [str(exc)] if settings.DEBUG else ["An unexpected error occurred"],
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(contacts.router, prefix="/contacts", tags=["Contacts"])
app.include_router(debts.router, prefix="/debts", tags=["Debts"])


# Root endpoint
@app.get("/")
def read_root():
    return success_response(
        message=f"{settings.APP_NAME} is running",
        data={
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "status": "healthy",
            "debug_mode": settings.DEBUG
        }
    )


# Health check
@app.get("/health")
def health_check():
    return success_response("API is healthy", {
        "database": "connected",
        "email_configured": bool(settings.MAIL_USERNAME and settings.MAIL_PASSWORD),
        "debug_mode": settings.DEBUG
    })


# Email configuration check (only in debug mode)
if settings.DEBUG:
    @app.get("/debug/email-config")
    def check_email_config():
        """Debug endpoint to check email configuration"""
        return success_response("Email configuration", {
            "mail_username_set": bool(settings.MAIL_USERNAME),
            "mail_password_set": bool(settings.MAIL_PASSWORD),
            "mail_from_set": bool(settings.MAIL_FROM),
            "mail_username": settings.MAIL_USERNAME if settings.MAIL_USERNAME else "NOT SET",
            "warning": "Make sure you're using an app-specific password for Gmail, not your regular password!"
        })