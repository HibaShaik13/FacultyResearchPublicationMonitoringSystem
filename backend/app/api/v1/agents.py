"""Agent monitoring and orchestration endpoints."""
from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session_factory
from app.models.agent import SyncRun, AgentRun
from app.models.user import User
from app.api.v1.auth import get_current_user
from app.orchestrator.pipeline_orchestrator import PipelineOrchestrator

router = APIRouter()

@router.get("/status")
async def agent_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get live status and throughput metrics of all 13 agents."""
    orchestrator = PipelineOrchestrator(db)
    return await orchestrator.get_pipeline_status()

async def _run_pipeline_background(user_id: Optional[Any] = None):
    async with async_session_factory() as session:
        orch = PipelineOrchestrator(session)
        await orch.run_full_pipeline(triggered_by=user_id, trigger="manual_admin_trigger")

@router.post("/sync/run")
async def trigger_full_sync(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger an end-to-end full synchronization cycle (Admin/Reviewer only)."""
    if current_user.role not in ("admin", "research_admin", "reviewer"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only research administrators can trigger a full pipeline synchronization."
        )

    orchestrator = PipelineOrchestrator(db)
    # Run synchronously or in background
    stats = await orchestrator.run_full_pipeline(triggered_by=current_user.id, trigger="admin_manual")
    return {
        "message": "Full synchronization completed successfully across all agents.",
        "stats": stats
    }

@router.get("/sync-runs")
async def list_sync_runs(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List recent sync runs with detailed agent metrics."""
    query = select(SyncRun).order_by(SyncRun.created_at.desc()).limit(limit)
    result = await db.execute(query)
    runs = result.scalars().all()
    return {
        "data": [
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

from pydantic import BaseModel
from app.models.user import User
from app.api.v1.auth import get_current_user
from app.agents.research_assistant_agent import ResearchAssistantAgent

class ChatRequest(BaseModel):
    message: str

@router.post("/chat")
async def agent_chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Research Assistant Agent (Agent 13) endpoint.
    Answers research, citation, verification, and accreditation questions using ground-truth database data.
    """
    assistant = ResearchAssistantAgent(db, current_user)
    result = await assistant.answer_query(req.message)
    return {
        "reply": result["answer"],
        "citations": result.get("citations", []),
        "provenance": result.get("provenance", "VFSTR Verified Database"),
        "suggested_actions": result.get("suggested_actions", [])
    }
