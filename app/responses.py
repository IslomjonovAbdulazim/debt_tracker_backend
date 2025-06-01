from fastapi import HTTPException
from typing import Any, Dict, List, Optional
from datetime import datetime

def success_response(message: str, data: Any = None, status_code: int = 200) -> Dict[str, Any]:
    """Create success response"""
    return {
        "success": True,
        "message": message,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }

def error_response(message: str, errors: List[str] = None, status_code: int = 400):
    """Raise HTTP exception with error response"""
    detail = {
        "success": False,
        "message": message,
        "errors": errors or [],
        "timestamp": datetime.utcnow().isoformat()
    }
    raise HTTPException(status_code=status_code, detail=detail)