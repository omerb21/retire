"""
Employment Module - Aggregated Router
Combines all employment-related routers into a single router
"""
from fastapi import APIRouter
from . import employer, grants, severance, termination

# Create main router
router = APIRouter()

# Include all sub-routers
router.include_router(employer.router)
router.include_router(grants.router)
router.include_router(severance.router)
router.include_router(termination.router)

__all__ = ['router']
