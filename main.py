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
from auth_utils import test_smtp_connection

# Load environment variables
load_dotenv()

# Configure logging for production
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app with enhanced configuration
app = FastAPI(
    title=os.getenv("APP_NAME", "Simple Debt Tracker"),
    description="A simple debt tracking API with secure email authentication",
    version=os.getenv("APP_VERSION", "1.0.0"),
    docs_url="/docs" if os.getenv("DEBUG", "False").lower() == "true" else None,
    redoc_url="/redoc" if os.getenv("DEBUG", "False").lower() == "true" else None,
)

# Add CORS middleware with production settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)


# Global exception handlers for better error reporting
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


# Startup event with enhanced initialization
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    try:
        logger.info("🚀 Starting Simple Debt Tracker API...")

        # Create database tables
        create_tables()
        logger.info("✅ Database tables initialized")

        # Test SMTP connection
        smtp_test = test_smtp_connection()
        if smtp_test["success"]:
            logger.info("✅ SMTP connection test successful")
        else:
            logger.warning(f"⚠️ SMTP connection test failed: {smtp_test['message']}")
            logger.warning("Email functionality may not work properly")

            # Log configuration errors for debugging
            if "errors" in smtp_test:
                for error in smtp_test["errors"]:
                    logger.error(f"SMTP Config Error: {error}")

        logger.info("🎉 Application startup completed successfully")

    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    logger.info("🛑 Shutting down Simple Debt Tracker API...")


# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(contacts.router, prefix="/contacts", tags=["Contacts"])
app.include_router(debts.router, prefix="/debts", tags=["Debts"])


# Root endpoint with system information
@app.get("/")
def read_root():
    """Root endpoint with system information"""
    return {
        "message": "Simple Debt Tracker API is running!",
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "documentation": "/docs" if os.getenv("DEBUG", "False").lower() == "true" else "disabled",
        "status": "healthy",
        "endpoints": {
            "health": "/health",
            "authentication": "/auth/*",
            "contacts": "/contacts/*",
            "debts": "/debts/*"
        }
    }


# Enhanced health check
@app.get("/health")
def health_check():
    """Comprehensive health check"""
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

    # Test SMTP configuration
    smtp_test = test_smtp_connection()
    smtp_status = "healthy" if smtp_test["success"] else "degraded"

    overall_status = "healthy"
    if db_status == "unhealthy":
        overall_status = "unhealthy"
    elif smtp_status == "degraded":
        overall_status = "degraded"

    return {
        "status": overall_status,
        "timestamp": "2025-06-02T00:00:00Z",
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "services": {
            "database": db_status,
            "email": smtp_status
        },
        "message": "API is working" if overall_status == "healthy" else "Some services may be degraded"
    }


# System information endpoint (debug only)
@app.get("/system-info")
def system_info():
    """System information for debugging"""
    if os.getenv("DEBUG", "False").lower() != "true":
        return {"message": "System info only available in debug mode"}

    smtp_test = test_smtp_connection()

    return {
        "environment": {
            "app_name": os.getenv("APP_NAME", "Simple Debt Tracker"),
            "environment": os.getenv("ENVIRONMENT", "development"),
            "debug": os.getenv("DEBUG", "False"),
            "log_level": os.getenv("LOG_LEVEL", "INFO")
        },
        "smtp_config": smtp_test.get("config", {}),
        "smtp_status": smtp_test["success"],
        "smtp_message": smtp_test["message"]
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