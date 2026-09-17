"""
FastAPI application factory.
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import close_db
from app.scheduler import start_scheduler, stop_scheduler
from app.api.router import api_router
from app.api.v1 import health

logger = logging.getLogger("rfms")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Application starting: %s (%s)", settings.app_name, settings.app_env)

    # Start background scheduler
    try:
        start_scheduler()
        logger.info("Background research monitoring scheduler started")
    except Exception as exc:
        logger.warning("Could not start background scheduler: %s", exc)

    # Automatically ensure required baseline accounts exist (idempotent, safe on every startup)
    try:
        from app.database import async_session_factory
        from app.seed.bootstrap import ensure_baseline_accounts
        async with async_session_factory() as session:
            await ensure_baseline_accounts(session)
    except Exception as exc:
        logger.warning("Could not complete startup account verification: %s", exc)

    yield

    # Shutdown
    try:
        stop_scheduler()
    except Exception as exc:
        logger.warning("Error during scheduler shutdown: %s", exc)

    try:
        await close_db()
    except Exception as exc:
        logger.warning("Error during database shutdown: %s", exc)
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "Agentic AI system for automated discovery, verification, and monitoring "
            "of institutional faculty research publications."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Root health endpoint (for direct /health probes)
    app.include_router(health.router, tags=["Health"])

    # API routes (prefixed with /api)
    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
