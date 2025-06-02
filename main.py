from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import logging
import asyncio
from contextlib import asynccontextmanager

from app.config import settings
from app.database import create_tables
from app.responses import success_response
from app.routers import auth, contacts, debts

# Set up logging with improved format
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Background task for cleanup
async def cleanup_task():
    """Background cleanup task"""
    while True:
        try:
            from app.auth import cleanup_temp_codes
            cleanup_temp_codes()
            # Run cleanup every 5 minutes
            await asyncio.sleep(300)
        except Exception as e:
            logger.error(f"Cleanup task error: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan manager"""
    # Startup
    logger.info("Starting Debt Tracker API...")

    # Create database tables
    try:
        create_tables()
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

    # Start background cleanup task
    cleanup_task_handle = None
    if settings.ENABLE_TEMP_CODE_FALLBACK:
        cleanup_task_handle = asyncio.create_task(cleanup_task())
        logger.info("Background cleanup task started")

    # Test email configuration on startup
    try:
        from app.auth import test_email_configuration
        email_test = test_email_configuration()
        if email_test["success"]:
            logger.info("✅ Email configuration test passed")
        else:
            logger.warning(f"⚠️ Email configuration issue: {email_test['message']}")
    except Exception as e:
        logger.warning(f"Email configuration test failed: {e}")

    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} started successfully")
    logger.info(f"Environment: {settings.SERVER_ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    yield

    # Shutdown
    logger.info("Shutting down Debt Tracker API...")
    if cleanup_task_handle:
        cleanup_task_handle.cancel()
        try:
            await cleanup_task_handle
        except asyncio.CancelledError:
            pass
    logger.info("Shutdown complete")


# Create FastAPI app with lifespan
app = FastAPI(
    title=settings.APP_NAME,
    description="A fast and reliable debt tracking API with email verification and fallback mechanisms",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# Optimized error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
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
    """Handle validation errors"""
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


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle database errors"""
    logger.error(f"Database error: {str(exc)}")

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Database error occurred",
            "errors": [str(exc)] if settings.DEBUG else ["Database temporarily unavailable"],
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors"""
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
        message=f"{settings.APP_NAME} is running smoothly",
        data={
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "status": "healthy",
            "debug_mode": settings.DEBUG,
            "environment": settings.SERVER_ENVIRONMENT,
            "features": {
                "email_fallback": settings.ENABLE_TEMP_CODE_FALLBACK,
                "background_emails": settings.ENABLE_BACKGROUND_EMAILS,
                "manual_verification": settings.ALLOW_MANUAL_VERIFICATION and settings.DEBUG
            }
        }
    )


# Optimized health check
@app.get("/health")
def health_check():
    """Quick health check"""
    return success_response("API is healthy", {
        "database": "connected",
        "email_configured": bool(settings.MAIL_USERNAME and settings.MAIL_PASSWORD),
        "debug_mode": settings.DEBUG,
        "environment": settings.SERVER_ENVIRONMENT,
        "uptime": "operational"
    })


# Enhanced health check
@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check including email service"""
    from app.auth import test_email_configuration, check_network_connectivity

    health = {
        "database": "unknown",
        "email": "unknown",
        "network": "unknown",
        "environment": settings.SERVER_ENVIRONMENT,
        "debug_mode": settings.DEBUG,
        "timestamp": datetime.utcnow().isoformat()
    }

    # Test database
    try:
        from app.database import engine
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        health["database"] = "healthy"
    except Exception as e:
        health["database"] = "unhealthy"
        health["database_error"] = str(e)

    # Test network connectivity
    try:
        if check_network_connectivity():
            health["network"] = "healthy"
        else:
            health["network"] = "limited"
            health["network_note"] = "Cannot reach Gmail SMTP"
    except Exception as e:
        health["network"] = "unhealthy"
        health["network_error"] = str(e)

    # Test email configuration
    try:
        if settings.MAIL_USERNAME and settings.MAIL_PASSWORD:
            email_test = test_email_configuration()
            health["email"] = "healthy" if email_test["success"] else "unhealthy"
            health["email_message"] = email_test["message"]
        else:
            health["email"] = "not_configured"
            health["email_message"] = "Email credentials not provided"
    except Exception as e:
        health["email"] = "unhealthy"
        health["email_error"] = str(e)

    return success_response("Detailed health check completed", health)


# Debug endpoints (only in debug mode)
if settings.DEBUG:
    @app.get("/debug/config")
    def debug_config():
        """Debug endpoint to check configuration"""
        return success_response("Configuration check", {
            "email": {
                "username_set": bool(settings.MAIL_USERNAME),
                "password_set": bool(settings.MAIL_PASSWORD),
                "from_set": bool(settings.MAIL_FROM),
                "username": settings.MAIL_USERNAME if settings.MAIL_USERNAME else "NOT SET",
                "skip_send": settings.SKIP_EMAIL_SEND,
                "rate_limit": settings.EMAIL_RATE_LIMIT,
                "timeout": settings.EMAIL_TIMEOUT,
                "max_retries": settings.EMAIL_MAX_RETRIES
            },
            "features": {
                "background_emails": settings.ENABLE_BACKGROUND_EMAILS,
                "temp_code_fallback": settings.ENABLE_TEMP_CODE_FALLBACK,
                "manual_verification": settings.ALLOW_MANUAL_VERIFICATION,
                "emergency_bypass": settings.EMERGENCY_BYPASS_EMAIL
            },
            "performance": {
                "email_timeout": settings.EMAIL_TIMEOUT,
                "network_check_timeout": settings.NETWORK_CHECK_TIMEOUT,
                "log_level": settings.LOG_LEVEL
            }
        })


    @app.get("/debug/test-email")
    async def test_email_endpoint():
        """Debug endpoint to test email configuration"""
        from app.auth import test_email_configuration

        result = test_email_configuration()
        return success_response("Email test completed", {
            "result": result,
            "note": "Check inbox if successful"
        })


    @app.post("/debug/test-network")
    async def test_network():
        """Test network connectivity"""
        from app.auth import check_network_connectivity

        try:
            can_reach_gmail = check_network_connectivity()
            return success_response("Network test completed", {
                "gmail_smtp_reachable": can_reach_gmail,
                "status": "connected" if can_reach_gmail else "limited",
                "note": "Gmail SMTP connectivity test"
            })
        except Exception as e:
            return success_response("Network test failed", {
                "error": str(e),
                "status": "error"
            })


    @app.get("/debug/temp-codes")
    async def debug_temp_codes():
        """Check temporary codes (debug only)"""
        from app.auth import temp_codes

        active_codes = {}
        for email, data in temp_codes.items():
            active_codes[email] = {
                "code_type": data["code_type"],
                "expires_at": data["expires_at"].isoformat(),
                "created_at": data["created_at"].isoformat(),
                "expired": data["expires_at"] < datetime.utcnow()
            }

        return success_response("Temporary codes status", {
            "active_count": len(active_codes),
            "codes": active_codes
        })


# Performance monitoring
@app.get("/metrics")
async def get_metrics():
    """Basic performance metrics"""
    return success_response("System metrics", {
        "email_service": {
            "provider": "gmail_smtp",
            "rate_limit": settings.EMAIL_RATE_LIMIT,
            "timeout": settings.EMAIL_TIMEOUT,
            "max_retries": settings.EMAIL_MAX_RETRIES,
            "fallback_enabled": settings.ENABLE_TEMP_CODE_FALLBACK
        },
        "database": {
            "type": "sqlite" if "sqlite" in settings.DATABASE_URL else "other",
            "pool_size": settings.DB_POOL_SIZE
        },
        "environment": settings.SERVER_ENVIRONMENT,
        "version": settings.APP_VERSION
    })


# Emergency bypass endpoint (only if enabled)
if settings.EMERGENCY_BYPASS_EMAIL and settings.DEBUG:
    @app.post("/emergency/bypass-email-verification")
    async def emergency_bypass_verification():
        """Emergency endpoint to bypass email verification"""
        logger.warning("EMERGENCY: Email verification bypass used")
        return success_response("Emergency bypass available", {
            "warning": "This is an emergency endpoint",
            "use_manual_verify": "/auth/manual-verify endpoint available",
            "note": "Only available in debug mode"
        })