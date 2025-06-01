# app/utils/responses.py
from fastapi import HTTPException, status
from typing import Any, Dict, List, Optional
from datetime import datetime

def success_response(
    message: str,
    data: Any = None,
    status_code: int = 200
) -> Dict[str, Any]:
    """Create standardized success response"""
    return {
        "success": True,
        "message": message,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
        "status_code": status_code
    }

def error_response(
    message: str,
    errors: Optional[List[str]] = None,
    error_code: Optional[str] = None,
    status_code: int = 400
) -> Dict[str, Any]:
    """Create standardized error response"""
    return {
        "success": False,
        "message": message,
        "errors": errors or [],
        "error_code": error_code,
        "timestamp": datetime.utcnow().isoformat(),
        "status_code": status_code
    }

def paginated_response(
    message: str,
    data: List[Any],
    page: int = 1,
    per_page: int = 10,
    total: int = 0
) -> Dict[str, Any]:
    """Create paginated response"""
    return {
        "success": True,
        "message": message,
        "data": data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
            "has_next": page * per_page < total,
            "has_prev": page > 1
        },
        "timestamp": datetime.utcnow().isoformat()
    }

def validation_error_response(errors: List[str]) -> Dict[str, Any]:
    """Create validation error response"""
    return error_response(
        message="Validation failed",
        errors=errors,
        error_code="VALIDATION_ERROR",
        status_code=422
    )

def not_found_response(resource: str = "Resource") -> Dict[str, Any]:
    """Create not found error response"""
    return error_response(
        message=f"{resource} not found",
        error_code="NOT_FOUND",
        status_code=404
    )

def unauthorized_response() -> Dict[str, Any]:
    """Create unauthorized error response"""
    return error_response(
        message="Authentication required",
        error_code="UNAUTHORIZED",
        status_code=401
    )

def forbidden_response(message: str = "Access forbidden") -> Dict[str, Any]:
    """Create forbidden error response"""
    return error_response(
        message=message,
        error_code="FORBIDDEN",
        status_code=403
    )

def conflict_response(message: str) -> Dict[str, Any]:
    """Create conflict error response"""
    return error_response(
        message=message,
        error_code="CONFLICT",
        status_code=409
    )

def too_many_requests_response() -> Dict[str, Any]:
    """Create rate limit error response"""
    return error_response(
        message="Too many requests. Please try again later.",
        error_code="RATE_LIMIT",
        status_code=429
    )

def server_error_response() -> Dict[str, Any]:
    """Create server error response"""
    return error_response(
        message="Internal server error. Please try again later.",
        error_code="SERVER_ERROR",
        status_code=500
    )

# Helper function to raise standardized HTTP exceptions
def raise_http_error(
    status_code: int,
    message: str,
    errors: Optional[List[str]] = None,
    error_code: Optional[str] = None
):
    """Raise HTTPException with standardized error format"""
    detail = error_response(
        message=message,
        errors=errors,
        error_code=error_code,
        status_code=status_code
    )
    raise HTTPException(status_code=status_code, detail=detail)