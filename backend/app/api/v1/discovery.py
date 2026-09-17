"""Discovery pipeline endpoints."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent import SyncRun
from app.models.user import User
from app.api.v1.auth import get_current_user
from app.orchestrator.pipeline_orchestrator import PipelineOrchestrator

router = APIRouter()


@router.get("/runs")
async def list_discovery_runs(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List past and current discovery runs."""
    query = select(SyncRun).order_by(SyncRun.created_at.desc()).limit(limit)
    result = await db.execute(query)
    runs = result.scalars().all()
    return {
        "runs": [
            {
                "id": str(r.id),
                "run_type": r.run_type,
                "status": r.status,
                "trigger": r.trigger,
                "publications_discovered": r.publications_discovered,
                "publications_merged": r.publications_merged,
                "publications_verified": r.publications_verified,
                "review_tasks_created": r.review_tasks_created,
                "errors_count": r.errors_count,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in runs
        ]
    }


@router.post("/trigger")
async def trigger_discovery(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger a full multi-agent discovery and research metrics sync."""
    if current_user.role not in ("admin", "research_admin", "reviewer"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators and reviewers can trigger publication discovery.",
        )

    orchestrator = PipelineOrchestrator(db)
    stats = await orchestrator.run_full_pipeline(
        triggered_by=current_user.id,
        trigger="manual_discovery_trigger",
    )
    return {
        "message": "Discovery and synchronization pipeline completed successfully.",
        "sync_run_id": stats.get("sync_run_id"),
        "status": stats.get("sync_run_status", "completed"),
        "stats": stats,
    }


@router.get("/status")
async def discovery_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current discovery pipeline status and agent execution health."""
    orchestrator = PipelineOrchestrator(db)
    return await orchestrator.get_pipeline_status()
