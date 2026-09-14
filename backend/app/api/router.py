"""
Main API router — aggregates all v1 endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1 import health, faculty, publications, discovery, review, reports, analytics, agents, auth, notifications

api_router = APIRouter()

# Health check
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(health.router, prefix="/v1/health", tags=["Health"])

# V1 API routes
api_router.include_router(auth.router, prefix="/v1/auth", tags=["Authentication"])
api_router.include_router(faculty.router, prefix="/v1/faculty", tags=["Faculty"])
api_router.include_router(publications.router, prefix="/v1/publications", tags=["Publications"])
api_router.include_router(discovery.router, prefix="/v1/discovery", tags=["Discovery"])
api_router.include_router(review.router, prefix="/v1/review", tags=["Review"])
api_router.include_router(reports.router, prefix="/v1/reports", tags=["Reports"])
api_router.include_router(analytics.router, prefix="/v1/analytics", tags=["Analytics"])
api_router.include_router(agents.router, prefix="/v1/agents", tags=["Agents"])
api_router.include_router(notifications.router, prefix="/v1/notifications", tags=["Notifications"])

