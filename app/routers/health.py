"""
Health check router for API status monitoring
"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health_check():
    """
    Simple health check endpoint to verify API is running
    """
    return {"status": "ok", "message": "API is running"}
