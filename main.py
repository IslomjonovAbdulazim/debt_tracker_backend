from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import os
import logging
from dotenv import load_dotenv

from database import create_tables
from routers import auth, contacts, debts
from resend_email_service import resend_service

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=os.getenv("APP_NAME", "Simple Debt Tracker"),
    description="A simple debt tracking API with Resend email authentication",
    version=os.getenv("APP_VERSION", "1.0.0"),
    docs_url="/docs" if os.getenv("DEBUG", "False").lower() == "true" else None,
    redoc_url="/redoc" if os.getenv("DEBUG", "False").lower() == "true" else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions"""
    logger.error(f"HTTP {exc.status_code} error on {request.url}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "error_code": exc.status_code
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    logger.error(f"Validation error on {request.url}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Invalid request data",
            "errors": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors"""
    logger.error(f"Unexpected error on {request.url}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "error": "An unexpected error occurred" if os.getenv("DEBUG", "False").lower() != "true" else str(exc)
        }
    )


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    try:
        logger.info("🚀 Starting Simple Debt Tracker API...")

        # Create database tables
        create_tables()
        logger.info("✅ Database tables initialized")

        # Test Resend email service
        email_test = resend_service.test_connection()
        if email_test["success"]:
            logger.info(f"✅ Resend email service ready: {email_test.get('provider', 'Resend')}")
        else:
            logger.warning(f"⚠️ Resend email service test failed: {email_test.get('error', 'unknown error')}")
            logger.warning("Email functionality may not work properly")

        logger.info("🎉 Application startup completed successfully")

    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise


# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(contacts.router, prefix="/contacts", tags=["Contacts"])
app.include_router(debts.router, prefix="/debts", tags=["Debts"])


# Root endpoint
@app.get("/")
def read_root():
    """Root endpoint with system information"""
    return {
        "message": "Simple Debt Tracker API is running!",
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "email_provider": "Resend",
        "documentation": "/docs" if os.getenv("DEBUG", "False").lower() == "true" else "disabled",
        "status": "healthy",
        "endpoints": {
            "health": "/health",
            "authentication": "/auth/*",
            "contacts": "/contacts/*",
            "debts": "/debts/*",
            "email_test": "/auth/smtp-test",
            "email_info": "/auth/email-service-info"
        }
    }


# Enhanced health check
@app.get("/health")
def health_check():
    """Comprehensive health check including email service"""
    try:
        # Test database connection
        from database import SessionLocal
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"

    # Test Resend email service
    email_test = resend_service.test_connection()
    email_status = "healthy" if email_test["success"] else "degraded"

    overall_status = "healthy"
    if db_status == "unhealthy":
        overall_status = "unhealthy"
    elif email_status == "degraded":
        overall_status = "degraded"

    return {
        "status": overall_status,
        "timestamp": "2025-06-03T00:00:00Z",
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "services": {
            "database": db_status,
            "email": email_status
        },
        "email_provider": "Resend",
        "message": "All services operational" if overall_status == "healthy" else "Some services may be degraded"
    }


# System information endpoint
@app.get("/system-info")
def system_info():
    """System information for debugging"""
    if os.getenv("DEBUG", "False").lower() != "true":
        return {"message": "System info only available in debug mode"}

    email_test = resend_service.test_connection()

    return {
        "environment": {
            "app_name": os.getenv("APP_NAME", "Simple Debt Tracker"),
            "environment": os.getenv("ENVIRONMENT", "development"),
            "debug": os.getenv("DEBUG", "False"),
            "log_level": os.getenv("LOG_LEVEL", "INFO")
        },
        "email_service": {
            "provider": "Resend",
            "from_email": resend_service.from_email,
            "from_name": resend_service.from_name,
            "api_key_configured": bool(resend_service.api_key),
            "status": email_test["success"],
            "message": email_test.get("message", email_test.get("error", "Unknown"))
        }
    }


if __name__ == "__main__":
    import uvicorn

    # Production-ready server configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    workers = int(os.getenv("WORKERS", "1"))

    logger.info(f"Starting server on {host}:{port}")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
        access_log=True
    )