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
            "debug_mode": settings.DEBUG,
            "environment": settings.SERVER_ENVIRONMENT
        }
    )


# Health check
@app.get("/health")
def health_check():
    return success_response("API is healthy", {
        "database": "connected",
        "email_configured": bool(settings.MAIL_USERNAME and settings.MAIL_PASSWORD),
        "debug_mode": settings.DEBUG,
        "environment": settings.SERVER_ENVIRONMENT
    })


# Enhanced health check with email testing
@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check including email service"""
    from app.auth import test_email_configuration

    health = {
        "database": "unknown",
        "email": "unknown",
        "environment": settings.SERVER_ENVIRONMENT,
        "debug_mode": settings.DEBUG
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

    # Test email configuration
    try:
        if settings.MAIL_USERNAME and settings.MAIL_PASSWORD:
            email_results = await test_email_configuration()
            health["email"] = "healthy" if "✅" in str(email_results) else "unhealthy"
            health["email_details"] = email_results
        else:
            health["email"] = "not_configured"
            health["email_details"] = ["Email credentials not provided"]
    except Exception as e:
        health["email"] = "unhealthy"
        health["email_error"] = str(e)

    return success_response("Detailed health check completed", health)


# Email testing endpoints (only in debug mode)
if settings.DEBUG:
    @app.get("/debug/email-config")
    def check_email_config():
        """Debug endpoint to check email configuration"""
        return success_response("Email configuration", {
            "mail_username_set": bool(settings.MAIL_USERNAME),
            "mail_password_set": bool(settings.MAIL_PASSWORD),
            "mail_from_set": bool(settings.MAIL_FROM),
            "mail_username": settings.MAIL_USERNAME if settings.MAIL_USERNAME else "NOT SET",
            "skip_email_send": settings.SKIP_EMAIL_SEND,
            "rate_limit": settings.EMAIL_RATE_LIMIT,
            "rate_window": settings.EMAIL_RATE_WINDOW,
            "verification_expiry": settings.EMAIL_VERIFICATION_EXPIRY,
            "password_reset_expiry": settings.PASSWORD_RESET_EXPIRY,
            "warning": "Make sure you're using an app-specific password for Gmail, not your regular password!"
        })


    @app.get("/debug/test-email")
    async def test_email_sending():
        """Debug endpoint to test email sending"""
        from app.auth import test_email_configuration

        try:
            results = await test_email_configuration()
            return success_response("Email test completed", {
                "results": results,
                "note": "Check your email inbox for the test message"
            })
        except Exception as e:
            return success_response("Email test failed", {
                "error": str(e),
                "suggestion": "Check your email configuration and network connectivity"
            })


    @app.get("/debug/test-rate-limit")
    async def test_rate_limit():
        """Test rate limiting functionality"""
        from app.auth import EmailRateLimiter

        email = "test@example.com"
        results = []

        for i in range(5):
            limited = EmailRateLimiter.is_rate_limited(email)
            results.append(f"Request {i + 1}: {'BLOCKED' if limited else 'ALLOWED'}")

        # Reset for next test
        EmailRateLimiter.reset_rate_limit(email)

        return success_response("Rate limit test completed", {
            "results": results,
            "note": "First 3 requests should be ALLOWED, rest should be BLOCKED"
        })


    @app.post("/debug/send-test-otp")
    async def send_test_otp():
        """Send a test OTP email to the configured email address"""
        if not settings.MAIL_USERNAME:
            return success_response("Test failed", {
                "error": "MAIL_USERNAME not configured"
            })

        from app.auth import send_verification_email, generate_code

        try:
            test_code = generate_code()
            await send_verification_email(
                email=settings.MAIL_USERNAME,
                name="Test User",
                code=test_code
            )

            return success_response("Test OTP sent successfully", {
                "sent_to": settings.MAIL_USERNAME,
                "test_code": test_code,
                "note": "Check your email inbox"
            })
        except Exception as e:
            return success_response("Test OTP failed", {
                "error": str(e),
                "suggestion": "Check email configuration and server connectivity"
            })


# Email metrics endpoint
@app.get("/metrics/email")
async def get_email_metrics():
    """Get email sending metrics"""
    # In production, you might want to use a proper metrics system
    return success_response("Email metrics", {
        "email_service": "gmail_smtp",
        "rate_limit_configured": settings.EMAIL_RATE_LIMIT,
        "rate_window_seconds": settings.EMAIL_RATE_WINDOW,
        "verification_expiry_minutes": settings.EMAIL_VERIFICATION_EXPIRY,
        "password_reset_expiry_minutes": settings.PASSWORD_RESET_EXPIRY,
        "note": "Detailed metrics require proper monitoring setup"
    })