from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

from app.config import settings
from app.database import create_tables
from app.responses import success_response
from app.routers import auth, contacts, debts

# Create database tables
create_tables()

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="A simple debt tracking API",
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
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "errors": [str(exc)] if settings.DEBUG else [],
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
            "status": "healthy"
        }
    )


# Health check
@app.get("/health")
def health_check():
    return success_response("API is healthy")